package com.otc.pepper;

import android.content.Context;

import java.security.KeyStore;
import java.security.cert.Certificate;
import java.security.cert.CertificateException;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.List;

import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLSocketFactory;
import javax.net.ssl.TrustManager;
import javax.net.ssl.TrustManagerFactory;
import javax.net.ssl.X509TrustManager;

/**
 * Pepper's onboard Android 6.0 (API 23) predates Let's Encrypt's ISRG Root X2 (issued 2020), which
 * is what the Railway backend's certificate chains to - confirmed via adb logcat on the physical
 * robot: "CertPathValidatorException: Trust anchor for certification path not found", even though
 * the backend is fully reachable and healthy.
 *
 * Android's manifest-based networkSecurityConfig (the normal fix for this) only takes effect on API
 * 24+, so it's a no-op on this device. This builds a composite X509TrustManager instead - the
 * system's default trust manager plus the bundled Let's Encrypt roots - which works on any API
 * level because it's plain javax.net.ssl, not the OS-level config mechanism.
 */
final class TrustManagerUtil {
    private TrustManagerUtil() {}

    static SSLSocketFactory buildSslSocketFactory(Context ctx, X509TrustManager trustManager) throws Exception {
        SSLContext sslContext = SSLContext.getInstance("TLS");
        sslContext.init(null, new TrustManager[]{trustManager}, null);
        return sslContext.getSocketFactory();
    }

    static X509TrustManager buildCompositeTrustManager(Context ctx) throws Exception {
        X509TrustManager systemTrustManager = systemDefaultTrustManager();
        X509TrustManager bundledTrustManager = bundledRootsTrustManager(ctx);
        return new CompositeTrustManager(systemTrustManager, bundledTrustManager);
    }

    private static X509TrustManager systemDefaultTrustManager() throws Exception {
        TrustManagerFactory tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        tmf.init((KeyStore) null);
        for (TrustManager tm : tmf.getTrustManagers()) {
            if (tm instanceof X509TrustManager) return (X509TrustManager) tm;
        }
        throw new IllegalStateException("No system X509TrustManager available");
    }

    private static X509TrustManager bundledRootsTrustManager(Context ctx) throws Exception {
        CertificateFactory cf = CertificateFactory.getInstance("X.509");
        KeyStore keyStore = KeyStore.getInstance(KeyStore.getDefaultType());
        keyStore.load(null, null);

        int[] rawResIds = {R.raw.isrg_root_x1, R.raw.isrg_root_x2};
        String[] aliases = {"isrg_root_x1", "isrg_root_x2"};
        for (int i = 0; i < rawResIds.length; i++) {
            try (java.io.InputStream in = ctx.getResources().openRawResource(rawResIds[i])) {
                Certificate cert = cf.generateCertificate(in);
                keyStore.setCertificateEntry(aliases[i], cert);
            }
        }

        TrustManagerFactory tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        tmf.init(keyStore);
        for (TrustManager tm : tmf.getTrustManagers()) {
            if (tm instanceof X509TrustManager) return (X509TrustManager) tm;
        }
        throw new IllegalStateException("No bundled X509TrustManager available");
    }

    /** Trusts a chain if either the system store or the bundled Let's Encrypt roots accept it. */
    private static class CompositeTrustManager implements X509TrustManager {
        private final X509TrustManager first;
        private final X509TrustManager second;

        CompositeTrustManager(X509TrustManager first, X509TrustManager second) {
            this.first = first;
            this.second = second;
        }

        @Override
        public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
            first.checkClientTrusted(chain, authType);
        }

        @Override
        public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
            try {
                first.checkServerTrusted(chain, authType);
            } catch (CertificateException e) {
                second.checkServerTrusted(chain, authType);
            }
        }

        @Override
        public X509Certificate[] getAcceptedIssuers() {
            List<X509Certificate> combined = new ArrayList<>();
            combined.addAll(java.util.Arrays.asList(first.getAcceptedIssuers()));
            combined.addAll(java.util.Arrays.asList(second.getAcceptedIssuers()));
            return combined.toArray(new X509Certificate[0]);
        }
    }
}
