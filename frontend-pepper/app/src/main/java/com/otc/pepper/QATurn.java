package com.otc.pepper;

/** Mirrors frontend-app/src/types.ts QATurn. */
public class QATurn {
    public final int turnNumber;
    public final String queryText;
    public final String answerText;
    public final boolean inScope;

    public QATurn(int turnNumber, String queryText, String answerText, boolean inScope) {
        this.turnNumber = turnNumber;
        this.queryText = queryText;
        this.answerText = answerText;
        this.inScope = inScope;
    }
}
