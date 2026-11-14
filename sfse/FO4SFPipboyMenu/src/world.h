#pragma once

// FO4SFPipboyMenu world surface (FAL-250; README.md, "World surface"). main.cpp calls these only after its own checks
// passed (the runtime guard, the Address Library file, the IMenu ids, vtables and RTTI). With World=0, as shipped,
// every call returns at once and the log is #704's.
namespace World
{
	// reads World, WorldKey, WorldMenu and WorldMovie from the ini next to the dll: one step=world_config line, or one
	// "refuse step=world" line and the overlay probe runs alone. a_base and a_imageSize are main.cpp's checked image
	void Configure(const std::filesystem::path& a_ini, int a_stage, std::uint32_t a_menuKey, std::uintptr_t a_base,
		std::size_t a_imageSize);

	// on the main thread, once FO4SF_PipboyMenu is registered: the census of registered menus, then the world key
	void Start(const SFSE::TaskInterface* a_task);

	// SFSE's movie-created callback (its own IMenu::LoadMovie hook, after the engine's loader returned), every menu
	void OnMovieCreated(const RE::IMenu* a_menu);
}
