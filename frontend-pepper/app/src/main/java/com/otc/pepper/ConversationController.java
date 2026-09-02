package com.otc.pepper;

import com.aldebaran.qi.Future;
import com.aldebaran.qi.sdk.QiContext;
import com.aldebaran.qi.sdk.builder.SayBuilder;
import com.aldebaran.qi.sdk.object.conversation.Say;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Shared conversation logic used by both ChatActivity and AvatarChatActivity - the native
 * equivalent of frontend-app/src/hooks/useConversation.ts. Holds turn history, submits a turn to
 * /api/query/stream, and speaks each sentence through QiSDK Say (native TTS output, per the
 * decision to use Pepper's own speech instead of the backend's /api/tts proxy) as soon as it's
 * complete - instead of waiting for the whole answer to finish generating first. This is the same
 * latency win frontend-app's useConversation.ts/useTTS.speakStream() apply on the web side, just
 * without a separate audio-fetch step since Say generates its own audio on-robot.
 *
 * The on-screen transcript (see ChatActivity/AvatarChatActivity) still only updates once the full
 * answer is known, unlike the web's progressive "typing" effect - Pepper's speech is the primary
 * channel and the screen is secondary (see the "Passive TTS auto-narration" judgment call in
 * PEPPER_PARITY_CHANGES.md), so a live on-screen typing effect wasn't judged worth the extra
 * complexity here; only the speech-latency half of the web change was ported.
 */
public class ConversationController {

    public interface Listener {
        void onSubmitStart();
        void onTurnAdded(QATurn turn);
        void onSubmitError(String message);
        void onSpeakingStateChanged(boolean speaking);
    }

    // Matches a run of text ending in . ! or ? (plus trailing whitespace) - the same "sentence"
    // definition frontend-app/src/hooks/useConversation.ts uses to decide when a chunk of the
    // streaming answer is complete enough to hand to speech.
    private static final Pattern SENTENCE_PATTERN = Pattern.compile("[^.!?]*[.!?]+(?:\\s+|$)");
    private static final Object SPEECH_END = new Object();

    private final String sessionId;
    private final List<QATurn> history = new ArrayList<>();
    private final Listener listener;
    private volatile QiContext qiContext;
    private Future<Void> currentSayFuture;
    private volatile BlockingQueue<Object> sentenceQueue;
    // Bumped on every new submit() and on stopSpeaking(), so a superseded stream's speaker loop
    // (or a sentence still arriving from an old, cancelled stream) can tell it's stale and stop,
    // instead of talking over a newer answer - the same role frontend-app's useTTS.ts speechToken
    // plays for the web's audio playback queue.
    private volatile int speechToken = 0;

    public ConversationController(String sessionId, Listener listener) {
        this.sessionId = sessionId;
        this.listener = listener;
    }

    public void setQiContext(QiContext qiContext) {
        this.qiContext = qiContext;
    }

    public List<QATurn> getHistory() {
        return history;
    }

    public void submit(String text, String inputMethod) {
        if (text == null || text.trim().isEmpty()) return;
        String trimmed = text.trim();
        listener.onSubmitStart();

        int myToken = beginSpeechStream();
        StringBuilder unspoken = new StringBuilder();

        ApiClient.queryStream(sessionId, trimmed, inputMethod, new ApiClient.StreamCallback() {
            @Override
            public void onDelta(String delta) {
                unspoken.append(delta);
                String pending = unspoken.toString();
                Matcher m = SENTENCE_PATTERN.matcher(pending);
                int consumedUpTo = 0;
                while (m.find()) {
                    String sentence = pending.substring(m.start(), m.end()).trim();
                    if (!sentence.isEmpty()) enqueueSentence(myToken, sentence);
                    consumedUpTo = m.end();
                }
                unspoken.delete(0, consumedUpTo);
            }

            @Override
            public void onDone(ApiClient.QueryStreamResult result) {
                String remaining = unspoken.toString().trim();
                if (!remaining.isEmpty()) enqueueSentence(myToken, remaining);
                endSentenceStream(myToken);
                QATurn turn = new QATurn(result.turnNumber, trimmed, result.answerText, result.inScope);
                history.add(turn);
                listener.onTurnAdded(turn);
            }

            @Override
            public void onError(String message) {
                endSentenceStream(myToken);
                QATurn turn = new QATurn(history.size() + 1, trimmed,
                        "Sorry, something went wrong reaching the system. Please try again.", false);
                history.add(turn);
                listener.onTurnAdded(turn);
                listener.onSubmitError(message);
            }
        });
    }

    /** Stops whatever is currently queued/speaking and starts a fresh sentence queue + a
     * background "speaker" thread that consumes it in order, running one Say per sentence. */
    private synchronized int beginSpeechStream() {
        stopSpeaking();
        speechToken++;
        int myToken = speechToken;
        BlockingQueue<Object> queue = new LinkedBlockingQueue<>();
        sentenceQueue = queue;
        new Thread(() -> runSpeakerLoop(myToken, queue)).start();
        return myToken;
    }

    private void enqueueSentence(int token, String sentence) {
        if (token != speechToken) return; // this stream was superseded/stopped - drop it
        BlockingQueue<Object> queue = sentenceQueue;
        if (queue != null) queue.offer(sentence);
    }

    private void endSentenceStream(int token) {
        if (token != speechToken) return;
        BlockingQueue<Object> queue = sentenceQueue;
        if (queue != null) queue.offer(SPEECH_END);
    }

    /** Runs on its own background thread for the lifetime of one submit()'s speech: pulls
     * sentences off the queue in order and speaks each one fully before starting the next
     * (matching natural speech pacing), stopping as soon as a newer stream supersedes this one. */
    private void runSpeakerLoop(int myToken, BlockingQueue<Object> queue) {
        boolean spokeAny = false;
        try {
            while (true) {
                Object item = queue.take();
                if (myToken != speechToken) return; // superseded while waiting for the next sentence
                if (item == SPEECH_END) break;
                QiContext ctx = qiContext;
                if (ctx == null) continue; // no robot focus right now - skip this sentence rather than crash
                if (!spokeAny) {
                    spokeAny = true;
                    listener.onSpeakingStateChanged(true);
                }
                try {
                    Say say = SayBuilder.with(ctx).withText(Speech.wrap((String) item)).build();
                    currentSayFuture = say.async().run();
                    currentSayFuture.get();
                } catch (Exception ignored) {
                    // Cancellation or focus loss - not an error worth surfacing.
                }
                if (myToken != speechToken) return;
            }
        } catch (InterruptedException ignored) {
        } finally {
            if (myToken == speechToken && spokeAny) listener.onSpeakingStateChanged(false);
        }
    }

    public void stopSpeaking() {
        speechToken++; // supersedes any in-flight submit's stream and speaker loop
        BlockingQueue<Object> queue = sentenceQueue;
        if (queue != null) queue.offer(SPEECH_END); // unblock a speaker thread waiting in queue.take()
        if (currentSayFuture != null && !currentSayFuture.isDone()) {
            try {
                currentSayFuture.requestCancellation();
            } catch (Exception ignored) {
            }
        }
    }
}
