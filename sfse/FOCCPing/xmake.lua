-- FOCCPing, the B0 spike's SFSE plugin, as an xmake project in the shape of libxse/commonlibsf-template.
-- lib/commonlibsf is the libxse CommonLibSF checkout (pinned in build.ps1: 9d090c4, with its submodule
-- lib/commonlib-shared at 9fbb74d). build.ps1 builds from a copy of this folder in the staging folder and places the
-- checkout there as a directory junction, so nothing of the library is in the repo. The commonlibsf.plugin rule writes
-- the SFSE version data (the library's res/commonlibsf-plugin.cpp.in): the Address Library (SFSE's AddressLibraryV2
-- bit, the one SFSE 0.2.21 counts as address independence), the 1.14.70+ layout, CompatibleVersions RUNTIME_LATEST.
-- Nothing in src/ redeclares it.
includes("lib/commonlibsf")

set_project("FOCCPing")
set_version("0.3.0")
set_license("GPL-3.0")
set_languages("c++23")
set_warnings("allextra")

add_rules("mode.debug", "mode.releasedbg")

target("FOCCPing", function()
    add_rules("commonlibsf.plugin", {
        name = "FOCCPing",
        author = "fo4sf",
        description = "B0 bridge spike: the Papyrus native FOCC.Ping(v) answers v + 1"
    })
    -- the rule's after_build would copy the dll into a game or mods folder named by XSE_SF_GAME_PATH or
    -- XSE_SF_MODS_PATH; build.ps1 clears both and collects the dll from build/windows/x64/releasedbg itself, so a
    -- build installs nothing
    set_values("commonlib.plugin.install", false)

    add_files("src/**.cpp")
    add_headerfiles("src/**.h")
    add_includedirs("src")
    set_pcxxheader("src/pch.h")
end)
