package com.otc.pepper;

import com.aldebaran.qi.Future;
import com.aldebaran.qi.sdk.QiContext;
import com.aldebaran.qi.sdk.builder.SayBuilder;
import com.aldebaran.qi.sdk.object.conversation.Say;

import java.util.ArrayList;
import java.util.List;

/**
 * Shared conversation logic used by both ChatActivity and AvatarChatActivity - the native
 * equivalent of frontend-app/src/hooks/useConversation.ts. Holds turn history, submits a turn to
 * /api/query, and speaks the answer through QiSDK Say (native TTS output, per the decision to use
 * Pepper's own speech instead of the backend's /api/tts proxy).
 */
public class ConversationController {

    public interface Listener {
        void onSubmitStart();
        void onTurnAdded(QATurn turn);
        void onSubmitError(String message);
        void onSpeakingStateChanged(boolean speaking);
    }

    private final String sessionId;
    private final List<QATurn> history = new ArrayList<>();
    private final Listener listener;
    private volatile QiContext qiContext;
    private Future<Void> currentSayFuture;

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
        ApiClient.query(sessionId, trimmed, inputMethod, new ApiClient.ApiCallback<ApiClient.QueryResponse>() {
            @Override
            public void onSuccess(ApiClient.QueryResponse res) {
                QATurn turn = new QATurn(res.turnNumber, trimmed, res.answerText, res.inScope);
                history.add(turn);
                listener.onTurnAdded(turn);
                speak(res.answerText);
            }

            @Override
            public void onError(String message) {
                QATurn turn = new QATurn(history.size() + 1, trimmed,
                        "Sorry, something went wrong reaching the system. Please try again.", false);
                history.add(turn);
                listener.onTurnAdded(turn);
                listener.onSubmitError(message);
            }
        });
    }

    /** Runs Say on a background thread and reports speaking state via the listener, matching the
     * currentSayFuture pattern in Interledger's TalkToPepperActivity. */
    public void speak(String text) {
        QiContext ctx = qiContext;
        if (ctx == null) return;
        stopSpeaking();
        new Thread(() -> {
            listener.onSpeakingStateChanged(true);
            try {
                Say say = SayBuilder.with(ctx).withText(Speech.wrap(text)).build();
                currentSayFuture = say.async().run();
                currentSayFuture.get();
            } catch (Exception ignored) {
                // Cancellation or focus loss - not an error worth surfacing.
            } finally {
                listener.onSpeakingStateChanged(false);
            }
        }).start();
    }

    public void stopSpeaking() {
        if (currentSayFuture != null && !currentSayFuture.isDone()) {
            try {
                currentSayFuture.requestCancellation();
            } catch (Exception ignored) {
            }
        }
    }
}
