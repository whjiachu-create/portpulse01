#  Windowed Presenter Display Architecture

Summer/Fall 2020
DRI: Ryan Poling

## Overview

The windowed presenter display encompasses the main presenter display window (`KNMacWindowedPresenterDisplayWindowController`), and the keyboard shortcuts window (`KNMacWindowedPresenterDisplayShortcutsWindowController`) which is also sometimes called the 'help' window. The main window encompasses a vertical navigator in a collapsible sidebar on the leading edge, presenter notes on the bottom trailing edge, and a collapsible current/next region on the top trailing edge.

## KNMacWindowedPresenterDisplayController

The `KNMacWindowedPresenterDisplayController` is the top level class which is responsible for interfacing with the existing presentation architecture (`KNMacPlaybackPresentationController`, etc.). It has methods to show and hide the presenter display windows, as well as handling the beginning and ending of the presentation.

The `Combine` framework is used to handle many aspects of the UI and event handling.

## KNMacWindowedPresenterDisplayState

This is considered to be the data model for the windowed presenter display. In addition to providing access to the `KNDocumentRoot`, it is used to track the current event, displayed slide, etc.. Due to the Storyboard design, this data model must be propagated to most of the child view controllers to give them access to the information they need.

## KNMacWindowedPresenterDisplayWindowController

This class is responsible for the main presenter display window.

## KNMacWindowedPresenterDisplayStoryboard

We use a storyboard because it provides a lot of automatic handling of `NSSplitViewController` for us, specifically making it easy to set up a full height sidebar and automatically providing the correct appearance changes on Jazz and Golden Gate.

This storyboard sets up the sidebar, for the navigator; the main content area, which will later be set up to include the notes and current/next slide; and a toolbar which includes such controls as the ready indicator and the timer.

## KNMacWindowedPresenterDisplayMainContentStoryboard

This storyboard sets up the main content area which includes both the presenter notes (on the bottom), and the current/next on the top. Again this is in a split view. When the main content view from the `KNMacWindowedPresenterDisplayStoryboard` becomes visible, it automatically triggers a segue to load the `KNMacWindowedPresenterDisplayMainContentStoryboard` and embed its initial view controller in the content view.

### KNMacWindowedPresenterDisplayMainContentViewController

The `KNMacWindowedPresenterDisplayMainContentViewController` manages the trailing edge view managed by the `KNMacWindowedPresenterDisplaySidebarSplitViewController`. When its view appears, it automatically calls `performSegue` to embed the `KNMacWindowedPresenterDisplayMainContentSplitViewController` in its view.

### KNMacWindowedPresenterDisplayMainContentSplitViewController

The `KNMacWindowedPresenterDisplayMainContentSplitViewController` manages a top to bottom split view, with the current/next slide displayed on the top and the presenter notes displayed on the bottom.

## KNMacWindowedPresenterDisplayNavigatorCollectionViewController

Manages an `NSCollectionView` of slide thumbnails. Currently, it can be set to a single row which scrolls horizontally, or a full window view with multiple rows and columns which scrolls vertically.

A subscriber from `Combine` is used to automatically change the collection view layout when the user toggles the expansion control.

### KNMacWindowedPresenterDisplayNavigatorDataSource

Provides the slide thumbnails for the collection view.

### KNMacWindowedPresenterDisplayNavigatorItem

Represents a single item in the navigator collection view.

## KNMacWindowedPresenterDisplayShortcutsWindowController

This class is responsible for the shortcuts window.

### KNMacWindowedPresenterDisplayShortcutsView

A SwiftUI implementation of the shortcuts view.

