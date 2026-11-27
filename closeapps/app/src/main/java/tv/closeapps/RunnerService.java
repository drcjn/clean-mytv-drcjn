package tv.closeapps;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;
import android.widget.Toast;
import dadb.AdbKeyPair;
import dadb.Dadb;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;

/** Talks to the TV's own adbd on 127.0.0.1:5555 (network debugging stays on; the key is allowed once on the TV),
 *  which is how an ordinary app gets the shell rights needed to close other apps. */
public class RunnerService extends Service {
    static final String ACTION_BOOT = "tv.closeapps.BOOT";
    static final String ACTION_CLOSE = "tv.closeapps.CLOSE";
    private final Handler ui = new Handler(Looper.getMainLooper());

    @Override
    public IBinder onBind(Intent i) { return null; }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        nm.createNotificationChannel(new NotificationChannel("c", "Close Apps", NotificationManager.IMPORTANCE_MIN));
        startForeground(1, new Notification.Builder(this, "c").setSmallIcon(R.drawable.ic_close)
                .setContentTitle("Close Apps").build());
        final boolean close = intent != null && ACTION_CLOSE.equals(intent.getAction());
        new Thread(() -> {
            try {
                work(close);
            } finally {
                stopSelf(startId);
            }
        }).start();
        return START_NOT_STICKY;
    }

    private void toast(String s) { ui.post(() -> Toast.makeText(getApplicationContext(), s, Toast.LENGTH_LONG).show()); }

    private Dadb connect() throws Exception {
        File priv = new File(getFilesDir(), "adbkey"), pub = new File(getFilesDir(), "adbkey.pub");
        if (!priv.exists()) AdbKeyPair.generate(priv, pub);
        return Dadb.create("127.0.0.1", 5555, AdbKeyPair.read(priv, pub));
    }


    private void pushAsset(Dadb d, String asset, String remote, int mode) throws Exception {
        File f = new File(getCacheDir(), asset);
        try (InputStream in = getAssets().open(asset); FileOutputStream out = new FileOutputStream(f)) {
            byte[] buf = new byte[4096]; int r;
            while ((r = in.read(buf)) > 0) out.write(buf, 0, r);
        }
        d.push(f, remote, mode, System.currentTimeMillis());
    }

    private void work(boolean close) {
        int tries = close ? 3 : 40;           // at boot, adbd may start a little after us
        for (int n = 0; n < tries; n++) {
            try (Dadb d = connect()) {
                pushAsset(d, "autoclose.sh", "/data/local/tmp/autoclose.sh", 493);
                pushAsset(d, "apps.txt", "/data/local/tmp/autoclose.apps", 420);
                d.shell("setsid nohup sh /data/local/tmp/autoclose.sh >/dev/null 2>&1 < /dev/null & sleep 1");
                if (close) {
                    d.shell("for p in $(cat /data/local/tmp/autoclose.apps); do am kill $p; done");
                    toast("Other apps closed");
                }
                Log.i("CloseApps", "watcher ensured");
                return;
            } catch (Exception e) {
                Log.w("CloseApps", "attempt " + n + " failed", e);
                try { Thread.sleep(3000); } catch (InterruptedException ie) { return; }
            }
        }
        if (close) toast("Close Apps: allow USB debugging on the TV, and keep MiTV Adb debugging on");
    }
}
