#!/system/bin/sh
# Runs on the TV as the shell user (started by the Close Apps helper at every boot).
# When one of the apps listed in /data/local/tmp/autoclose.apps comes to the front, the other listed apps'
# background processes are closed (am kill never touches the app on screen).
PIDF=/data/local/tmp/autoclose.pid
APPF=/data/local/tmp/autoclose.apps
old=$(cat $PIDF 2>/dev/null)
if [ -n "$old" ] && grep -q autoclose "/proc/$old/cmdline" 2>/dev/null; then exit 0; fi
echo $$ > $PIDF
logcat -b events -T 1 wm_set_resumed_activity:I '*:S' 2>/dev/null | while read -r line; do
  APPS=$(cat $APPF 2>/dev/null)
  cur=${line#*\[0,}; cur=${cur%%/*}
  case " $APPS " in *" $cur "*) ;; *) continue ;; esac
  sleep 2
  for p in $APPS; do
    [ "$p" = "$cur" ] && continue
    [ -n "$(pidof $p)" ] && am kill $p
  done
done
