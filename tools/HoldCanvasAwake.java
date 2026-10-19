import android.content.Context;
import android.os.PowerManager;

/** Shell bridge companion: scoped to the native canvas display, never the phone panel. */
public class HoldCanvasAwake {
    public static void main(String[] args) throws Exception {
        android.os.Looper.prepareMainLooper();
        Class<?> thread = Class.forName("android.app.ActivityThread");
        Object instance = thread.getMethod("systemMain").invoke(null);
        Context context = (Context) thread.getMethod("getSystemContext").invoke(instance);
        PowerManager manager = (PowerManager) context.getSystemService(Context.POWER_SERVICE);
        int display = Integer.parseInt(args[0]);
        int seconds = Integer.parseInt(args[1]);
        PowerManager.WakeLock lock = (PowerManager.WakeLock) PowerManager.class
                .getMethod("newWakeLock", int.class, String.class, int.class)
                .invoke(manager, PowerManager.SCREEN_BRIGHT_WAKE_LOCK | PowerManager.ACQUIRE_CAUSES_WAKEUP, "CarLinkLab:NativeCanvas", display);
        if (seconds == 0) lock.acquire(); else lock.acquire(seconds * 1000L);
        System.out.println("Canvas wake lock acquired display=" + display + " seconds=" + seconds);
        android.hardware.display.DisplayManager displays = (android.hardware.display.DisplayManager)
                context.getSystemService(Context.DISPLAY_SERVICE);
        long deadline = android.os.SystemClock.elapsedRealtime() + seconds * 1000L;
        while ((seconds == 0 || android.os.SystemClock.elapsedRealtime() < deadline) && displays.getDisplay(display) != null) {
            Thread.sleep(1000);
        }
        if (lock.isHeld()) lock.release();
        System.exit(0);
    }
}
