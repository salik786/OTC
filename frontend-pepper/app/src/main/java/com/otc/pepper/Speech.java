package com.otc.pepper;

/**
 * Every SayBuilder call in the app should go through wrap() so the speaking rate stays consistent
 * and adjustable in one place. \rspd=N\ is a NAOqi TTS tag (see Interledger's TalkToPepperActivity)
 * - N is a percentage of normal speed. Default Pepper speech reads too fast for participants
 * processing new medical information, so this slows it down.
 */
final class Speech {
    private Speech() {}

    private static final int SPEED_PERCENT = 75;

    static String wrap(String text) {
        return "\\rspd=" + SPEED_PERCENT + "\\ " + text;
    }
}
