/** Compact role cards for common insect / Drosophila cell classes (evidence-bound prose). */

export type NeuronRole = {
  label: string;
  system: string;
  does: string;
  reads?: string;
  writes?: string;
};

const ROLES: Record<string, NeuronRole> = {
  EPG: {
    label: "Ellipsoid body–protocerebral bridge–gall (EPG)",
    system: "Central complex · heading compass",
    does: "Encodes the fly’s heading as a bump of activity around the ellipsoid body; anchors the internal compass.",
    reads: "Visual / wind / self-motion cues via ring and bridge partners",
    writes: "PEN, PEG, and other CX compass partners",
  },
  PEN: {
    label: "Protocerebral bridge–ellipsoid body–noduli (PEN)",
    system: "Central complex · compass update",
    does: "Updates the heading bump when the animal turns; couples bridge columns to ellipsoid body tiles.",
    reads: "Self-motion / angular velocity pathways",
    writes: "EPG and related compass tiles",
  },
  PEG: {
    label: "Protocerebral bridge–ellipsoid body–gall (PEG)",
    system: "Central complex · compass",
    does: "Links bridge columns to gall / EB; participates in heading circuit recurrence.",
  },
  Delta7: {
    label: "Δ7 / PB Δ7",
    system: "Central complex · inhibition",
    does: "Provides structured inhibition across bridge columns that shapes the compass bump.",
  },
  T4: {
    label: "T4 medulla motion detector",
    system: "Optic lobe · elementary motion detection",
    does: "Direction-selective neuron in the medulla; a building block of ON-pathway motion vision.",
    reads: "Local medullary visual channels",
    writes: "Lobula plate tangential / motion integration neurons",
  },
  T5: {
    label: "T5 medulla / lobula motion detector",
    system: "Optic lobe · elementary motion detection",
    does: "Direction-selective OFF-pathway counterpart to T4 in motion vision.",
  },
  LPi: {
    label: "Lobula plate intrinsic",
    system: "Optic lobe · motion integration",
    does: "Local circuit neuron in the lobula plate shaping wide-field motion signals.",
  },
  DNp: {
    label: "Descending neuron (DNp class)",
    system: "Brain → VNC · motor command",
    does: "Carries descending drive from brain circuits into ventral nerve cord motor networks.",
  },
  DN: {
    label: "Descending neuron",
    system: "Brain → VNC · motor command",
    does: "Relays higher-order decisions into spinal-like VNC circuits that control limbs and body.",
  },
  AN: {
    label: "Ascending neuron",
    system: "VNC → brain · feedback",
    does: "Sends ascending proprioceptive / state signals from the VNC back toward the brain.",
  },
  IN: {
    label: "Interneuron",
    system: "Local circuit",
    does: "Local or mid-range interneuron mediating computation within a neuropil.",
  },
  MN: {
    label: "Motor neuron",
    system: "VNC · muscle drive",
    does: "Drives muscle fibers; the final common path for movement.",
  },
  SA: {
    label: "Sensory afferent",
    system: "Sensory input",
    does: "Primary sensory neuron bringing peripheral signals into the CNS.",
  },
  CL1: {
    label: "CL1 (CX column neuron)",
    system: "Central complex · columnar",
    does: "Columnar CX neuron often tied to compass / navigation circuitry in insects.",
  },
  CL2: {
    label: "CL2 (CX column neuron)",
    system: "Central complex · columnar",
    does: "Columnar CX class; morphology and partners define subtype-specific roles.",
  },
  TB1: {
    label: "TB1 (tangential bridge)",
    system: "Central complex",
    does: "Tangential neuron spanning protocerebral bridge columns; shapes compass dynamics.",
  },
};

function normalizeType(raw: string): string {
  const s = raw.trim();
  if (!s) return "";
  const upper = s.toUpperCase();
  if (upper.startsWith("EPG")) return "EPG";
  if (upper.startsWith("PEN")) return "PEN";
  if (upper.startsWith("PEG")) return "PEG";
  if (upper.startsWith("DELTA7") || upper.startsWith("Δ7") || s.startsWith("Delta7")) return "Delta7";
  if (upper.startsWith("T4")) return "T4";
  if (upper.startsWith("T5")) return "T5";
  if (upper.startsWith("LPI")) return "LPi";
  if (upper.startsWith("DNP")) return "DNp";
  if (upper.startsWith("DN")) return "DN";
  if (upper.startsWith("AN")) return "AN";
  if (upper.startsWith("MN")) return "MN";
  if (upper.startsWith("SA") || upper.startsWith("SN")) return "SA";
  if (upper.startsWith("CL1")) return "CL1";
  if (upper.startsWith("CL2")) return "CL2";
  if (upper.startsWith("TB1") || upper.startsWith("TB")) return "TB1";
  if (upper.startsWith("IN") || upper.includes("INTER")) return "IN";
  return s.split(/[_\-\s]/)[0] || s;
}

export function describeNeuron(opts: {
  cellType?: string | null;
  name?: string | null;
  region?: string | null;
  degreeIn?: number;
  degreeOut?: number;
  hasSkeleton?: boolean;
}): NeuronRole & { key: string; connectivity: string } {
  const raw = String(opts.cellType || opts.name || "");
  const key = normalizeType(raw);
  const role =
    ROLES[key] ||
    ({
      label: raw || "Unclassified neuron",
      system: opts.region || "Nervous system (pack-local)",
      does: raw
        ? `Observed unit typed “${raw}” in this reconstruction. Role is inferred from cell class literature when known; otherwise treat partners and morphology as the primary evidence.`
        : "Observed unit in this pack. Inspect partners, degree, and morphology for functional clues — no invented circuit role.",
    } satisfies NeuronRole);

  const din = opts.degreeIn ?? 0;
  const dout = opts.degreeOut ?? 0;
  const connectivity =
    din + dout > 0
      ? `Synaptic neighborhood in this pack: ${din} upstream partner link(s), ${dout} downstream. ${
          opts.hasSkeleton ? "Morphology available in 3D." : "Graph-only in this view (no local skeleton yet)."
        }`
      : opts.hasSkeleton
        ? "Morphology present; no synaptic edges in this pack (morphology-only / projectome layer)."
        : "Listed in the catalog; open partners panel when edges exist.";

  return { key, ...role, connectivity };
}
