Scriptname FO4SF_V111Exit extends Quest
{Vault 111 exit sequence (FAL-461). Holds the stages in order: 5 terminal tried without the Pip-Boy, 10 Pip-Boy taken,
 20 terminal used with it, 30 cog door opened. The two activator scripts set them. NO properties: the ids are the tool's
 (dotnet/Vault111Exit), found with Game.GetFormFromFile. Not compiled offline.}

Event OnInit()
    Debug.Trace("FO4SF_V111Exit ready")
EndEvent
