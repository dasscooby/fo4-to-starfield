Scriptname FO4SF_V111DoorTerminal extends ObjectReference
{Placed on the cog door's control terminal. Without the Pip-Boy token: a message and stage 5 (as FO4's MQ102 stage 5).
 With it: the first use plugs in (stage 20), the next opens the cog door with SetOpen (stage 30). Each step needs the
 one before.}

int Property CogDoorId Auto
{The cog door (FO4 VltGearDoor01) in the port, plugin-local id.}
string Property DoorPlugin Auto
{The port plugin's file name.}

Event OnActivate(ObjectReference akActionRef)
    if akActionRef != Game.GetPlayer()
        return
    endif
    Quest exitQuest = Game.GetFormFromFile(0x800, "FO4SFVault111Exit.esp") as Quest
    Form tokenForm = Game.GetFormFromFile(0x801, "FO4SFVault111Exit.esp")
    if exitQuest == None || tokenForm == None
        Debug.Trace("FO4SF_V111DoorTerminal: the quest or the token does not resolve")
        return
    endif
    if Game.GetPlayer().GetItemCount(tokenForm) == 0
        exitQuest.SetStage(5)
        Debug.Notification("Access denied: this terminal needs a Pip-Boy")
        Debug.Trace("FO4SF_V111DoorTerminal: no Pip-Boy, stage 5")
        return
    endif
    if exitQuest.GetStageDone(30)
        Debug.Notification("The cog door is already open")
    elseif exitQuest.GetStageDone(20)
        ObjectReference cogDoor = Game.GetFormFromFile(CogDoorId, DoorPlugin) as ObjectReference
        if cogDoor == None
            Debug.Trace("FO4SF_V111DoorTerminal: the cog door " + DoorPlugin + ":" + CogDoorId + " does not resolve")
            Debug.Notification("The door control does not answer")
            return
        endif
        int before = cogDoor.GetOpenState()
        cogDoor.SetOpen(True)
        exitQuest.SetStage(30)
        Debug.Notification("Cog door opening")
        Debug.Trace("FO4SF_V111DoorTerminal: cog door open_state before=" + before + " after=" + cogDoor.GetOpenState() + ", stage 30")
    else
        exitQuest.SetStage(20)
        Debug.Notification("Pip-Boy linked: use the control again to open the door")
        Debug.Trace("FO4SF_V111DoorTerminal: plugged in, stage 20")
    endif
EndEvent
