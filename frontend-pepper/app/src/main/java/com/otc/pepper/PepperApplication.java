package com.otc.pepper;

import android.app.Application;
import android.content.Context;

/** Exists solely to give ApiClient a Context for loading the bundled root CA raw resources - see
 * TrustManagerUtil. */
public class PepperApplication extends Application {
    private static Context appContext;

    @Override
    public void onCreate() {
        super.onCreate();
        appContext = getApplicationContext();
    }

    static Context getContext() {
        return appContext;
    }
}
