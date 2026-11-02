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

; P9's package driver, the next rung after Go's PathToReference returned Failure in the Commonwealth and in vanilla
; QASmoke alike (1 Nov 2026): the way the game moves its own actors. The probe quest's alias 0 (P9Walker, optional,
; allow reserved) carries Starfield.esm's DefaultTraveltoLinkedRef (212FDB: Travel template, location "near linked
; ref" with no keyword, no conditions; read from Starfield.esm 1.16.244 on the PC). Travel sets the actor's linked ref
; to the target, forces the actor into the alias and re-evaluates its packages, so the alias package (above the base
; NPC's own) walks it there. A package has no return code: the samples after the go are the answer, and the
; `p9 package` line two seconds later names the package the actor then runs (2174939 = 212FDB when the alias took).
;   cgf "FOCC_P9Drive.Travel" <actor id, signed decimal> 1      to the player
;   cgf "FOCC_P9Drive.Travel" <actor id, signed decimal> 0      to FOCC_P9_Dest
;   cgf "FOCC_P9Drive.TravelEnd" <actor id, signed decimal>     out of the alias, linked ref cleared
Function Travel(int actorId, int toPlayer) global
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
    ReferenceAlias walker = q.GetAlias(0) as ReferenceAlias
    if a == None || target == None || walker == None
        q.Trace("p9 go refused actor=" + actorId + " target=" + what + " driver=package walker=" + (walker != None))
        return
    endif
    q.Trace("p9 context actor=" + a.GetFormID() + " target=" + what + " id=" + target.GetFormID() + " actorcell=" + q.Id(a.GetParentCell()) + " targetcell=" + q.Id(target.GetParentCell()))
    q.Trace("p9 state actor=" + a.GetFormID() + " loaded=" + a.Is3DLoaded() + " dead=" + a.IsDead() + " disabled=" + a.IsDisabled() + " targetdisabled=" + target.IsDisabled() + " package=" + q.Id(a.GetCurrentPackage()))
    float t0 = Utility.GetCurrentRealTime()
    q.Trace("p9 go actor=" + a.GetFormID() + " call=" + t0 + " target=" + what + " id=" + target.GetFormID() + " dist=" + a.GetDistance(target) + " driver=package")
    a.SetLinkedRef(target)
    walker.ForceRefTo(a)
    a.EvaluatePackage()
    Utility.Wait(2.0)
    q.Trace("p9 package actor=" + a.GetFormID() + " call=" + t0 + " linked=" + q.Id(a.GetLinkedRef()) + " package=" + q.Id(a.GetCurrentPackage()) + " dist=" + a.GetDistance(target))
EndFunction

Function TravelEnd(int actorId) global
    FOCC_ProbeQuest q = FOCC_Probe.Q("p9")
    if q == None
        return
    endif
    Actor a = Game.GetForm(actorId) as Actor
    ReferenceAlias walker = q.GetAlias(0) as ReferenceAlias
    if a == None || walker == None
        q.Trace("p9 package end refused actor=" + actorId)
        return
    endif
    walker.Clear()
    a.SetLinkedRef(None)
    a.EvaluatePackage()
    q.Trace("p9 package cleared actor=" + a.GetFormID() + " package=" + q.Id(a.GetCurrentPackage()))
EndFunction

; P9's linked-ref driver (job focc-P9l). The package rung of 1 Nov 2026 (#644) found the actor walking under Starfield's
; own default master packages once its linked ref was set, never under the alias package: DefaultMaster_PatrolPackage
; (301C3 = 197059) to a linked marker, DefaultMaster_FollowPackage (301C5 = 197061) to a linked player. Link tests that
; alone: SetLinkedRef and EvaluatePackage, no alias. Its `p9 package` line two seconds later names the package then run.
;   cgf "FOCC_P9Drive.Link" <actor id, signed decimal> 1      to the player
;   cgf "FOCC_P9Drive.Link" <actor id, signed decimal> 0      to FOCC_P9_Dest
;   cgf "FOCC_P9Drive.LinkEnd" <actor id, signed decimal>     the link cleared
Function Link(int actorId, int toPlayer) global
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
        q.Trace("p9 go refused actor=" + actorId + " target=" + what + " driver=link")
        return
    endif
    q.Trace("p9 context actor=" + a.GetFormID() + " target=" + what + " id=" + target.GetFormID() + " actorcell=" + q.Id(a.GetParentCell()) + " targetcell=" + q.Id(target.GetParentCell()))
    q.Trace("p9 state actor=" + a.GetFormID() + " loaded=" + a.Is3DLoaded() + " dead=" + a.IsDead() + " disabled=" + a.IsDisabled() + " targetdisabled=" + target.IsDisabled() + " package=" + q.Id(a.GetCurrentPackage()))
    float t0 = Utility.GetCurrentRealTime()
    q.Trace("p9 go actor=" + a.GetFormID() + " call=" + t0 + " target=" + what + " id=" + target.GetFormID() + " dist=" + a.GetDistance(target) + " driver=link")
    a.SetLinkedRef(target)
    a.EvaluatePackage()
    Utility.Wait(2.0)
    q.Trace("p9 package actor=" + a.GetFormID() + " call=" + t0 + " linked=" + q.Id(a.GetLinkedRef()) + " package=" + q.Id(a.GetCurrentPackage()) + " dist=" + a.GetDistance(target))
EndFunction

Function LinkEnd(int actorId) global
    FOCC_ProbeQuest q = FOCC_Probe.Q("p9")
    if q == None
        return
    endif
    Actor a = Game.GetForm(actorId) as Actor
    if a == None
        q.Trace("p9 link end refused actor=" + actorId)
        return
    endif
    a.SetLinkedRef(None)
    a.EvaluatePackage()
    q.Trace("p9 link cleared actor=" + a.GetFormID() + " package=" + q.Id(a.GetCurrentPackage()))
EndFunction

; Keeps the actor loaded on a long rung: every 5 s, for `seconds`, the player is set `behind` metres back from the
; actor along the main axis of the line from the marker (P9Dest) through the actor, so a route east, west, north or
; south works (the sessions hop along one axis; no square root: Math is unverified in Starfield; without a marker,
; along -X as before), 5 m above the higher of the actor and the player (tgm: the fall is harmless), so the actor stays
; inside the loaded cells; the 1 Nov 330 m walk was unloaded in 79 of 130 samples. It moves only the player, never the
; actor. The higher of the two: on 1 Nov (run A2) the actor stepped 6 m down into the dry quarry east of Red Rocket and
; stopped there, and the actor's height + 5 m put the player about 2 m under the ground on the rim behind it; the
; player's own height (on that rim, a hop ago) keeps it above. Each hop where the player stands more than 5 m above
; the actor is logged (`p9 shadow rim`). The owner (1 Nov): that quarry changes by a scripted event; routes avoid it.
; The first hop waits 3 s: on the PC (1 Nov) a hop typed in a console batch closed the console, and the batch's closing
; key then reopened it, pausing the game (both long rungs). The wait lets the batch close the console first.
;   cgf "FOCC_P9Drive.Shadow" <actor id, signed decimal> <seconds> <behind m>
Function Shadow(int actorId, float seconds, float behind) global
    FOCC_ProbeQuest q = FOCC_Probe.Q("p9")
    if q == None
        return
    endif
    Actor a = Game.GetForm(actorId) as Actor
    Actor p = Game.GetPlayer()
    if a == None
        q.Trace("p9 shadow refused actor=" + actorId)
        return
    endif
    Utility.Wait(3.0)
    float t0 = Utility.GetCurrentRealTime()
    int hops = 0
    q.Trace("p9 shadow start actor=" + a.GetFormID() + " seconds=" + seconds + " behind=" + behind)
    ObjectReference dest = q.P9Dest
    float ux = -1.0
    float uy = 0.0
    float dx = 0.0
    float dy = 0.0
    float adx = 0.0
    float ady = 0.0
    float az = 0.0
    float pz = 0.0
    while Utility.GetCurrentRealTime() - t0 < seconds
        if dest != None
            dx = a.GetPositionX() - dest.GetPositionX()
            dy = a.GetPositionY() - dest.GetPositionY()
            adx = dx
            if adx < 0.0
                adx = -dx
            endif
            ady = dy
            if ady < 0.0
                ady = -dy
            endif
            if adx + ady > 1.0
                ux = 0.0
                uy = 0.0
                if adx >= ady
                    ux = 1.0
                    if dx < 0.0
                        ux = -1.0
                    endif
                else
                    uy = 1.0
                    if dy < 0.0
                        uy = -1.0
                    endif
                endif
            endif
        endif
        az = a.GetPositionZ()
        pz = p.GetPositionZ()
        if pz > az
            if pz > az + 5.0                  ; where the old rule (the actor's height + 5 m) put the player underground
                q.Trace("p9 shadow rim actor=" + a.GetFormID() + " actor_z=" + az + " player_z=" + pz)
            endif
            az = pz
        endif
        p.SetPosition(a.GetPositionX() + ux * behind, a.GetPositionY() + uy * behind, az + 5.0)
        hops += 1
        Utility.Wait(5.0)
    endwhile
    q.Trace("p9 shadow done actor=" + a.GetFormID() + " hops=" + hops)
EndFunction
