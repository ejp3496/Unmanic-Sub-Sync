This plugin will sync external SRT files with video files using FFSubSync by smacke.

It will attempt sync a given .srt file with any video file within the same directory with the same file name.

If a corresponding video file is not found, no action will be performed.

---

##### Links:

- [Github]()
- [ffsubsync](https://github.com/smacke/ffsubsync)

---

##### Additional Information:

**tip:**

in order for this plugin to operate ffsubsync must be installed with ```pip install ffsubsync```.
If you are using docker make a Dockerfile with the following lines.
```commandline
FROM josh5/unmanic:latest
RUN pip install ffsubsync
```