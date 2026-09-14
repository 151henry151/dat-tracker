import {
  BarChart,
  Callout,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Grid,
  H1,
  H2,
  H3,
  Pill,
  Row,
  Stack,
  Stat,
  Table,
  Text,
  useHostTheme,
} from "cursor/canvas";

/**
 * Strategic diagnosis of dat-tracker calibration quality.
 * Scores from 2026-09-09 plans on disk; failure taxonomy from hyp↔known analysis.
 */
export default function DatTrackerQualityDiagnosis() {
  const { tokens: t } = useHostTheme();

  return (
    <Stack gap={24} style={{ maxWidth: 960, margin: "0 auto", padding: 24 }}>
      <Stack gap={8}>
        <H1>dat-tracker — why it isn’t a working POC yet</H1>
        <Text tone="secondary" size="small">
          Diagnosis from current plans on disk, prior-agent HANDOFF, and pipeline
          review. Shipping gates are locked in PLAN.md; version stays in the
          0.1.x line until gates pass.
        </Text>
      </Stack>

      <Callout tone="warning">
        The sparse Gemini loop is built and runs end-to-end, but calibration is
        far from shippable. The dominant unused lever is placement polish
        (near-misses 15–60s early), not “add more silence detection.” Oracle
        snap45 on train alone jumps mean F1 0.687 → 0.846.
      </Callout>

      <Grid columns={4} gap={12}>
        <Stat
          value="0.687"
          label="Tier B train mean F1"
          tone="warning"
        />
        <Stat
          value="0.569"
          label="Tier B holdout mean F1"
          tone="danger"
        />
        <Stat
          value="0.374"
          label="Tier A mean F1 (3 shows)"
          tone="danger"
        />
        <Stat
          value="0.85 / 0.80"
          label="Gates (B holdout / A)"
          tone="info"
        />
      </Grid>

      <H2>Distance to gates</H2>
      <BarChart
        categories={[
          "B train",
          "B holdout",
          "Tier A",
          "B gate",
          "A gate",
          "Oracle snap45 (train)",
        ]}
        series={[
          {
            name: "Mean F1 @ ±15s",
            data: [0.687, 0.569, 0.374, 0.85, 0.8, 0.846],
          },
        ]}
        height={220}
      />
      <Text tone="secondary" size="small">
        Source: score_tier_b_plans / score_tier_a_plans on cached plans;
        oracle = move each hyp mid-cut to nearest known within 45s (no new cuts).
      </Text>

      <H2>What the other agent proved</H2>
      <Grid columns={2} gap={12}>
        <Card>
          <CardHeader>Real gains (keep)</CardHeader>
          <CardBody>
            <Stack gap={6}>
              <Text size="small">
                Near-zero merge bug fixed; gap-fill probe cap + ±45s clips;
                sparse multi-probe; mid-song INSERT prompt; temperature 0.0;
                segue guidance added.
              </Text>
              <Text size="small">
                Train track |Δ|≤1 → 100%. Mean F1 0.644 → 0.687. Variance
                reduced but not eliminated (los still swings).
              </Text>
            </Stack>
          </CardBody>
        </Card>
        <Card>
          <CardHeader>What they did not unlock</CardHeader>
          <CardBody>
            <Stack gap={6}>
              <Text size="small">
                Near-miss placement (the snap45 lever) was diagnosed earlier and
                never implemented as a non-oracle fix.
              </Text>
              <Text size="small">
                Effort went into far-miss / gap-fill. That helps min F1 later,
                but cannot alone reach 0.85 when ~26% of known mids are
                near-misses.
              </Text>
            </Stack>
          </CardBody>
        </Card>
      </Grid>

      <H2>Failure taxonomy (Tier B train mid-cuts)</H2>
      <Text tone="secondary" size="small">
        31 known mid-cuts across 5 train shows: matched @15s / near-miss 15–60s /
        far (&gt;60s or unmatched).
      </Text>
      <BarChart
        categories={["Matched ≤15s", "Near-miss 15–60s", "Far miss"]}
        series={[{ name: "Known mid-cuts", data: [18, 8, 5] }]}
        height={180}
      />

      <Table
        headers={["Show", "F1", "snap45", "match / near / far", "Mode"]}
        rows={[
          [
            "sbb2001",
            "0.889",
            "0.889",
            "2 / 0 / 0",
            "One spurious FP; otherwise fine",
          ],
          [
            "los1997-04",
            "0.769",
            "0.923",
            "3 / 1 / 0",
            "Early near-miss; volatile across runs",
          ],
          [
            "lke2006",
            "0.720",
            "0.880",
            "7 / 2 / 2",
            "Missed banter island; some far",
          ],
          [
            "ymsb2007",
            "0.533",
            "0.667",
            "2 / 1 / 2",
            "Wrong lattice; REJECTs near truth",
          ],
          [
            "crnml2002",
            "0.522",
            "0.870",
            "4 / 4 / 1",
            "Systematic early song-end cuts",
          ],
        ]}
        rowTone={[
          "success",
          undefined,
          undefined,
          "danger",
          "danger",
        ]}
      />

      <H2>Architectural bottlenecks</H2>
      <Stack gap={10}>
        <Card>
          <CardHeader trailing={<Pill tone="deleted" size="sm">critical</Pill>}>
            First listen is ±8s; truth is often 15–40s away
          </CardHeader>
          <CardBody>
            <Text size="small">
              Candidates often land on song-end / applause. The true etree cut
              (next banter/song start) is outside the first-listen clip, so Flash
              cannot hear it. Refine windows are wider (±20–60s) but refine is
              optional and still inherits an early-biased cut.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill tone="warning" size="sm">prompt</Pill>}>
            ACCEPT criteria still says “song ends”
          </CardHeader>
          <CardBody>
            <Text size="small">
              tracking_listen_prompt tells the model ACCEPT on “song ends / new
              song starts …” and later says place at next-track start. Notes on
              crnml show SNAP to “song ends / banter starts” — matching the early
              bias. The prompt fights itself.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill tone="warning" size="sm">post</Pill>}>
            Classical snaps are a double-edged sword
          </CardHeader>
          <CardBody>
            <Text size="small">
              Listen-center / silence snaps can close near-misses or yank a good
              cut onto a false energy peak. Blind snap-to-nearest classical
              feature failed experiments; any polish needs a directional rule
              (prefer later onset after low energy), not nearest-any-peak.
            </Text>
          </CardBody>
        </Card>
        <Card>
          <CardHeader trailing={<Pill tone="info" size="sm">missing</Pill>}>
            No few-shot / RAG; no applause vs music head
          </CardHeader>
          <CardBody>
            <Text size="small">
              PLAN calls for multi-corpus examples and music/speech/applause
              classifiers. Every show gets the same static prompt. The model
              has no Jon-style exemplars of “cut here, not 20s earlier.”
            </Text>
          </CardBody>
        </Card>
      </Stack>

      <H2>Significant bets — ranked</H2>
      <Table
        headers={["Bet", "Why it could move the needle", "Risk"]}
        rows={[
          [
            "A. Next-track-start placement pass",
            "Fix early bias in prompt + default wider refine; optional drift-forward after low-energy/applause toward speech/music onset. Targets the +0.16 oracle lift.",
            "Overshoot into mid-next-song if drift is blind",
          ],
          [
            "B. Two-clip scrub per candidate",
            "Listen at candidate and at candidate+25–35s (or a short sweep). Gives the model the song-end AND the next start without full-show upload.",
            "2× listen cost; need clear SNAP semantics",
          ],
          [
            "C. Few-shot from train known cuts",
            "Attach 2–3 labeled transition clips from other train shows (“cut at banter start, not applause peak”). Teaches packaging policy.",
            "Leak if holdout examples used; keep train-only",
          ],
          [
            "D. Lattice / track-budget from setlist priors",
            "When J-card or expected track count exists, constrain ACCEPT count and force denser probes. Helps ymsb/JMP under-seg and Pro collapse.",
            "Wrong priors hurt; Live Bluegrass often lacks setlist",
          ],
          [
            "E. Stop Pro from erasing mid cuts",
            "Escalate may refine/gap-fill but must not drop a well-spaced Flash lattice (JMP 3/11). Necessary for Tier A, not for train mean.",
            "Low risk if merge-only",
          ],
          [
            "F. Local boundary classifier later",
            "Train a small onset/boundary head on synthetic re-splits + Gemini labels. Long-term PLAN Phase 2b — not the next week’s bet.",
            "Needs data plumbing; synthetic≠Tier A",
          ],
        ]}
      />

      <H2>Recommended campaign (next 1–2 weeks)</H2>
      <Stack gap={8}>
        <Row gap={8} align="center">
          <Pill tone="info" active>1</Pill>
          <Text>
            Make “next track start, not song end” unambiguous in first-listen
            and refine prompts; remove “song ends” as an ACCEPT reason.
          </Text>
        </Row>
        <Row gap={8} align="center">
          <Pill tone="info" active>2</Pill>
          <Text>
            Default a forward placement pass: for each mid cut, search
            [cut, cut+45s] for speech onset or silence-end→onset; only move if
            energy dips then rises (TDD on crnml’s four near-misses).
          </Text>
        </Row>
        <Row gap={8} align="center">
          <Pill tone="info" active>3</Pill>
          <Text>
            Widen first-listen half-window (e.g. 8→20s) or add a second clip
            +25s ahead for candidates the model ACCEPT/SNAP’d at song-end.
          </Text>
        </Row>
        <Row gap={8} align="center">
          <Pill tone="info" active>4</Pill>
          <Text>
            Add 2–3 train-only few-shot transition clips into the prompt.
            Re-score train with 2+ runs per show at temperature 0.0.
          </Text>
        </Row>
        <Row gap={8} align="center">
          <Pill tone="info" active>5</Pill>
          <Text>
            Only then: far-miss/ymsb lattice + Pro collapse guards; re-run
            holdout once and Tier A. Do not batch zip todo.
          </Text>
        </Row>
      </Stack>

      <Divider />

      <H3>What not to do</H3>
      <Stack gap={4}>
        <Text size="small">
          Blind snap-to-nearest energy/speech (already hurt). Aggressive
          default gap-fill. Tuning on holdout. Full-show Gemini uploads as the
          happy path. Declaring victory from a single noisy run.
        </Text>
        <Text size="small" tone="secondary">
          Pipeline architecture is not the blocker — decision quality at
          transitions is. Fix placement policy so the model (or a
          constrained post-pass) consistently chooses next-track starts.
        </Text>
      </Stack>
    </Stack>
  );
}
