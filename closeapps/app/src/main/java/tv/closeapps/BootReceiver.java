package tv.closeapps;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** After every boot, start the on-TV watcher that closes the other streaming apps when one is opened. */
public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context c, Intent i) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(i.getAction())) {
            c.startForegroundService(new Intent(c, RunnerService.class).setAction(RunnerService.ACTION_BOOT));
        }
    }
}
