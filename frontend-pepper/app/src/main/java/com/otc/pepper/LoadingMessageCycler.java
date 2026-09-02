package com.otc.pepper;

import android.os.Handler;
import android.os.Looper;
import android.widget.TextView;

/**
 * Cycles a TextView's text through a small set of loading messages every 1.5s while active -
 * native port of frontend-app/src/hooks/useLoadingMessage.ts. Makes the "waiting for an answer"
 * status feel alive instead of a single static "Thinking..." line for however long generation
 * takes, matching the tablet's rotating loading indicator.
 */
public class LoadingMessageCycler {
    private static final String[] MESSAGES = {
            "Thinking...", "Checking the leaflet...", "Finding the best answer...", "Almost there..."
    };
    private static final long INTERVAL_MS = 1500;

    private final TextView target;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private int index;
    private boolean active;

    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            if (!active) return;
            index = (index + 1) % MESSAGES.length;
            target.setText(MESSAGES[index]);
            handler.postDelayed(this, INTERVAL_MS);
        }
    };

    public LoadingMessageCycler(TextView target) {
        this.target = target;
    }

    public void start() {
        if (active) return;
        active = true;
        index = 0;
        target.setText(MESSAGES[0]);
        handler.postDelayed(tick, INTERVAL_MS);
    }

    public void stop() {
        active = false;
        handler.removeCallbacks(tick);
    }
}
