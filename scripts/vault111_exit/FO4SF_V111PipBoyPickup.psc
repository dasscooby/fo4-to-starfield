Scriptname FO4SF_V111PipBoyPickup extends ObjectReference
{Placed over the Pip-Boy on the skeleton's arm. The player takes it: they get the token FO4SF_V111PipBoyToken once, the
 quest FO4SF_V111Exit goes to stage 10, and this reference disables itself. NO properties; ids are the tool's.}

Event OnActivate(ObjectReference akActionRef)
    if akActionRef != Game.GetPlayer()
        return
    endif
    Quest exitQuest = Game.GetFormFromFile(0x800, "FO4SFVault111Exit.esp") as Quest
    Form tokenForm = Game.GetFormFromFile(0x801, "FO4SFVault111Exit.esp")
    if exitQuest == None || tokenForm == None
        Debug.Trace("FO4SF_V111PipBoyPickup: the quest or the token does not resolve")
        return
    endif
    Actor playerRef = Game.GetPlayer()
    if playerRef.GetItemCount(tokenForm) == 0
        playerRef.AddItem(tokenForm, 1, True)
    endif
    exitQuest.SetStage(10)
    Debug.Notification("Pip-Boy 3000 Mark IV taken")
    Debug.Trace("FO4SF_V111PipBoyPickup: taken, stage 10")
    Disable()
EndEvent
