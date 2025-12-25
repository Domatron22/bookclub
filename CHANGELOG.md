# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2024-12-24

### Added

#### Core System
- Session-based authentication
- Unique 8-character club codes for easy joining
- Club creation with name, description, and settings
- Member management with display names

#### Book Management System
- Book suggestion system with title, author, and description
- Random selection support
- Admin-configurable book veto system with configurable thresholds (5-100%, increments of 5%)
- Admin-configurable voting system for book selection
- Currently reading status display
- Reading history/archive of completed books
- Reading tracker - members can join/leave current book
- Expandable reader lists showing who read each book
- Historical reader data preserved after book completion

#### Discussion System
- Discussion threads for each book
- Infinite-depth comment nesting (recursive comments)
- Like functionality on posts and comments at all levels
- Spoiler protection with click-to-reveal
- Real-time comment counts
- Collapsible comment threads

#### Review System
- 5-star rating system for books
- Text reviews with star ratings
- Average rating calculation and display
- Infinite-depth comment nesting on reviews
- Like functionality on reviews and comments
- Review statistics (rating averages, review counts)

#### Meeting System
- Meeting schedule setup with rotation patterns
- Automatic host rotation system
- Meeting creation with date, time, location, and description
- RSVP system with Yes/No/Maybe options
- Potluck coordination (members can list what they're bringing)
- Attendee lists with RSVP status
- Calendar view of all meetings
- iCalendar (.ics) export for calendar apps
- Next meeting display on club homepage

#### Admin System
- Club admin roles with promotion/demotion
- Veto system configuration (enable/disable, percentage threshold)
- Book selection method configuration (random vs voting)
- Voting threshold configuration with sliders and text input
- Member management (promote to admin, view all members)

#### User Interface
- Dark mode support (light/dark/auto themes, Theme preference stored in cookies)
- System theme detection for auto mode
- Responsive design for mobile and desktop
- Member dropdown on club page with admin indicators
- Reading tracker with join/leave buttons
- Icon system using Font Awesome 6.4.0

## [1.0.1] - 2024-12-25

### Fixed
- Fixed users inablility to create new clubs

[Unreleased]: https://github.com/Domatron22/bookclub/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Domatron22/bookclub/releases/tag/v1.0.0
[1.0.1]: https://github.com/Domatron22/bookclub/releases/tag/v1.0.1