Scriptname FOCC_B0 Hidden
{Console entry points of B0, the plugin bridge spike (docs/combined-core-cpp-port.md section 4, the owner's call of
 28 Oct 2026: stack A first, B as the backup; docs/spikes/combined-core-probes.md, section B0). Each resolves the probe
 quest through FOCC_Probe.Q and answers on the "focc" user log, as every probe does.
   cgf "FOCC_B0.Gmst"         b0 gmst name=iFOCC_Pong value=<v>   the probe plugin's own game setting (GMST 0x855, int 7)
                              read back with Game.GetGameSettingInt: 7 before any plugin touched it; on the setting
                              route (stack B) the value the plugin wrote by its name
   cgf "FOCC_B0.Ping" 41      b0 ping sent=41, then b0 pong sent=41 got=<FOCC.Ping(41)>: 42 when FOCCPing.dll bound
                              the native (stack A), 0 when nothing did (an unbound native yields 0; Papyrus.0.log
                              names it). The ping line is also what a log-tailing plugin (stack B) reads.
   Click                      b0 click: the other direction, native to script (B0-3, FAL-246). FO4SFPipboyMenu.dll
                              asks the script VM to run it, with no arguments, after each click on its menu's button
                              (ClickCall=FOCC_B0.Click); the line is that click reaching the probe quest. Typed in the
                              console it logs the same line, so the session card never types it.
 Game.GetGameSettingInt is declared in Starfield's Game.psc (lines 217 to 221 on the PC, 28 Oct 2026); FOCC.Ping in
 FOCC.psc here. Compiled on its own by make_combined_probe.py (compile_b0.txt), so a refusal leaves only B0 out.}

Function Gmst() global
    FOCC_ProbeQuest q = FOCC_Probe.Q("b0")
    if q == None
        return
    endif
    q.Trace("b0 gmst name=iFOCC_Pong value=" + Game.GetGameSettingInt("iFOCC_Pong"))
EndFunction

Function Ping(int v) global
    FOCC_ProbeQuest q = FOCC_Probe.Q("b0")
    if q == None
        return
    endif
    q.Trace("b0 ping sent=" + v)
    int got = FOCC.Ping(v)
    q.Trace("b0 pong sent=" + v + " got=" + got)
EndFunction

Function Click() global
    FOCC_ProbeQuest q = FOCC_Probe.Q("b0")
    if q == None
        return
    endif
    q.Trace("b0 click")
EndFunction
