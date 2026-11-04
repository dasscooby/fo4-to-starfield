Scriptname FOCC_P9Drive Hidden
{P9's scripted driver (docs/spikes/combined-core-probes.md, P9): Actor.PathToReference called from Papyrus, not from
 the console. The PC's ladder (28 Oct 2026) showed the console's PathToRef never bringing a calm citizen 17 m to the
 player, and cf "Actor.PathToReference" never reaches the function (docs/actors/npc-navigation.md, N0_cf). The exe's
 script-function table lists PathToReference, and the PC's compile of the probe stage at main c0c3c96c (28 Oct 2026)
 settled the signature: the two-argument call of FO4 was refused with "argument afnormalizedrotationspeed is not
 specified and has no default value", so Starfield's Actor.psc declares PathToReference with three arguments, the
 ObjectReference, float afWalkRunPercent and float afNormalizedRotationSpeed, no default for the third. It is 1.0 here, read from its
 name as the full turning rate; what it does to the walk is for the ladder to show. make_combined_probe.py compiles
 this script on its own: a refusal leaves only this script out.
   cgf "FOCC_P9Drive.Go" <actor id, signed decimal> 1      the actor paths to the player
   cgf "FOCC_P9Drive.Go" <actor id, signed decimal> 0      the actor paths to FOCC_P9_Dest
 Run P9Track first: it samples the walk. Starfield's Actor.psc (line 490 on the PC, 28 Oct 2026) declares it
 `int Function PathToReference(ObjectReference aTarget, float afNormalizedSpeed, float afNormalizedRotationSpeed,
 float afTargetRadius=-1.0, bool abHardRadius=false) native`, latent ("doesn't return until the goal is reached or
 pathing" ends), with its codes as properties (lines 476 to 480): PathingResult_Success 0, Failure 1, Stopped 2,
 Cleared 3, Timeout 4. The return goes on the `p9 path returned` line as result= (the kit d ladder of 28 Oct returned
 after 2.89 s with the actor 26.7 m out and no code logged, so it could not tell a missing path from a stopped walk).
 The lines before and after the call carry the real time; both name the call by its start time (call=), since a latent
 return can land after the next rung's lines. cgf does not wait for a latent call (P8: three calls with waits ran
 at once from one console session), but the game is paused while the console is open: close it after the call.}

Function Go(int actorId, int toPlayer) global
    FOCC_ProbeQuest q = FOCC_Probe.Q("p9")
    if q == None
        return
    endif
    Actor a = Game.GetForm(actorId) as Actor
    ObjectReference target = q.P9Dest
    string what = "dest"
    if toPlayer != 0
        target = Game.GetPlayer()
        what = "player"
    endif
    if a == None || target == None
        q.Trace("p9 go refused actor=" + actorId + " target=" + what)
        return
    endif
    ; Diagnostic reads only: never change packages, enable AI or move the actor to force a pass.
    ; A vanilla-room failure needs these bindings before it can implicate the converted navmesh.
    q.Trace("p9 context actor=" + a.GetFormID() + " target=" + what + " id=" + target.GetFormID() + " actorcell=" + q.Id(a.GetParentCell()) + " targetcell=" + q.Id(target.GetParentCell()))
    q.Trace("p9 state actor=" + a.GetFormID() + " loaded=" + a.Is3DLoaded() + " dead=" + a.IsDead() + " disabled=" + a.IsDisabled() + " targetdisabled=" + target.IsDisabled() + " package=" + q.Id(a.GetCurrentPackage()))
    float t0 = Utility.GetCurrentRealTime()
    q.Trace("p9 go actor=" + a.GetFormID() + " call=" + t0 + " target=" + what + " id=" + target.GetFormID() + " dist=" + a.GetDistance(target))
    int r = a.PathToReference(target, 1.0, 1.0)
    q.Trace("p9 path returned actor=" + a.GetFormID() + " call=" + t0 + " target=" + what + " result=" + r + " after=" + (Utility.GetCurrentRealTime() - t0) + " dist=" + a.GetDistance(target))
EndFunction
