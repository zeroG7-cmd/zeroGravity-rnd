# Operator Learning Bridge v1.1

This version adds conservative multiple-choice detection. It requires a visible semantic “Correct” signal plus either a selected answer marked successful or an enabled Continue/Next control. Event IDs are persisted in extension storage to prevent duplicate XP.

Load this folder as an unpacked extension in Edge/Chrome. Add an `icon128.png` before enabling notifications, or remove `iconUrl` from `background.js`.
