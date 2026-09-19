# The 1-minute video (P7.5)

Rules: one minute, own voice. It is not a summary of the README, it is the argument. The two
figures already exist, so the video shows nothing that is not measured in the repo.

**The picture is built.** `uv run --extra figures python scripts/video_slides.py` writes five
1920x1080 slides and `reports/video/nobody_reads_the_bounce.mp4`, a silent 60 s cut that holds
each slide for exactly the length of its line below. Record the voice over that file in one
pass; nothing has to be edited to a beat. Slides 3 and 4 are the README's two figures whole and
unaltered, so the audience is shown precisely what the repository publishes, and slide 5 reads
its commit list out of `git log` rather than quoting it.

Every number spoken below appears in `README.md` and in a `reports/*.csv`. Nothing is rounded
in the speaker's favour.

---

**[0:00-0:08] — title card: "Nobody reads the bounce"**

> Coaches say the best rebounders read the bounce. On ten ACB games of SkillCorner's open
> tracking, nobody does.

**[0:08-0:24] — a still of a shot in flight, the spread numbers on screen**

> Knowing where the shot came from tells you almost nothing about where the ball lands. I
> measured the ball's own arrival too, and all that predicts is how far it is still carrying
> sideways. That is geometry, not a read.

**[0:24-0:42] — figure 1 fills the screen**

> So the rebound is not read, it is occupied. Within four feet of the rim, running at it lifts
> your chance of winning the board seventeen points, and thirty-two on five games I never
> touched. Past twelve feet, nothing.

**[0:42-0:52] — figure 2**

> And that is not proximity in disguise: hold the distance fixed, vary only the heading, and it
> still falls four and a half times.

**[0:52-1:00] — the repo, on the commit list**

> Every threshold was frozen and committed before I opened those five games. The ones that
> failed are in there too.

---

141 spoken words: 56 s at 150 words per minute, 63 s at 135, which is the realistic pace for a
script with numbers in it. Time a first take before recording; if it runs over, the first cut
is "measured here from broadcast tracking", then the last sentence
loses its ending. The last thing to cut is the ball's arrival: it is the one quantity measured here for the
first time, and it cost the repository an overturned finding and then a refuted overturn to
say it honestly.

Do not say "crash", "box out" or "tag up" anywhere in the video. The work measures vectors, not
intentions, and that ruling holds in the voiceover as much as in the code.
