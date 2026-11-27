package tv.closeapps;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;

/** The "Close Apps" tile: closes every streaming app's background process, then goes away. */
public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        startForegroundService(new Intent(this, RunnerService.class).setAction(RunnerService.ACTION_CLOSE));
        finish();
    }
}
