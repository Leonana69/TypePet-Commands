---
name: cheer
kind: pet
usage: /cheer [name]
help: The pet does a happy little cheer.
holdSeconds: 6
---
# one step per line: op args  (say takes the rest of the line; # lines are comments)
expression cheers 6
say Woohoo! Let's go {{args}}
