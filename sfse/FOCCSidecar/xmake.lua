-- FOCCSidecar, the P1 probe's SFSE plugin, as an xmake project in the shape of libxse/commonlibsf-template (FAL-216:
-- the library pin and build of FO4SFPipboyMenu, PR #704, and FOCCPing). lib/commonlibsf is the libxse CommonLibSF
-- checkout (pinned in build.ps1: 9d090c4, with its submodule lib/commonlib-shared at 9fbb74d). build.ps1 builds from a
-- copy of this folder in the staging folder and places the checkout there as a directory junction, so nothing of the
-- library is in the repo. The commonlibsf.plugin rule writes the SFSE version data (the library's
-- res/commonlibsf-plugin.cpp.in): the Address Library (SFSE's AddressLibraryV2 bit), the 1.14.70+ layout,
-- CompatibleVersions RUNTIME_LATEST. Nothing in src/ redeclares it. codec.h and sha256.cpp stay at this folder's top,
-- where tests/test_sfse_sidecar_codec.py and tests/test_combined_cpp_parity.py compile them on Linux.
includes("lib/commonlibsf")

set_project("FOCCSidecar")
set_version("0.3.0")
set_license("GPL-3.0")
set_languages("c++23")
set_warnings("allextra")

add_rules("mode.debug", "mode.releasedbg")

target("FOCCSidecar", function()
    add_rules("commonlibsf.plugin", {
        name = "FOCCSidecar",
        author = "fo4sf",
        description = "P1 probe: a sidecar file per save, written at PreSaveGame and read back at PostLoadGame"
    })
    -- the rule's after_build would copy the dll into a game or mods folder named by XSE_SF_GAME_PATH or
    -- XSE_SF_MODS_PATH; build.ps1 clears both and collects the dll from build/windows/x64/releasedbg itself, so a
    -- build installs nothing
    set_values("commonlib.plugin.install", false)

    add_files("src/**.cpp", "sha256.cpp")
    add_headerfiles("src/**.h", "codec.h", "runtime_dir.h", "sha256.h")
    add_includedirs("src", ".")
    set_pcxxheader("src/pch.h")
end)
