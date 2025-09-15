# Playback Toolbars Read Me

## Mac

For the Mac, there are several types of "toolbars", where most of them are not actually `NSToolbar` instances, but rather something else which behaves similarly from a UI perspective.

### Windowed

* **Windowed Playback Window Toolbar** 
This is an actual `NSToolbar` instance which is displayed at the top of the playback window when the user hovers the mouse over the title bar area of the window. It also displays the title as a toolbar item.

→ The `KNMacPlaybackWindowTitleToolbarProvider` provides this toolbar.

* **Windowed Presenter Display Toolbar**
This is an actual `NSToolbar` instance which is displayed at the top of the windowed presenter display window.

→ This toolbar is owned/created/managed by the `KNMacWindowedPresenterDisplayWindowController`.

### Full Screen

* **Full Screen Playback Window Floating Toolbar**
This is a floating 'toolbar' which appears at the bottom of the playback window when the mouse is brought to the very bottom (similar to macOS Dock behavior). It is not a 'real' toolbar, but rather a custom created cross-platform control.

→ This toolbar is represented by the `KNPlaybackFloatingToolbar`.

* **Full Screen Presenter Display Toolbar**
This exists at the top of the presenter display window, for a full screen play back. It is essentially a series of buttons which are laid out with autolayout.

→ This toolbar is represented by the `KNMacPresenterDisplayToolbarView`.

## iOS

TBD.
