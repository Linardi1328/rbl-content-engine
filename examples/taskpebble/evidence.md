# TaskPebble Synthetic Evidence

TaskPebble is a synthetic, public-safe fixture created only to test the RBL Content Engine pipeline.

## Verified project facts

- TaskPebble stores tasks in a local JSON file.
- Each task has a title and a completed boolean.
- The command `python taskpebble.py list` prints all tasks in creation order.
- The command `python taskpebble.py complete <number>` marks the selected task complete.

## Scope notes

- TaskPebble does not sync data to a remote service.
- TaskPebble does not send notifications.
