interface NarrativeStreamProps {
  narrative: string;
  streaming: boolean;
}

export function NarrativeStream({ narrative, streaming }: NarrativeStreamProps) {
  if (!narrative && !streaming) return null;

  return (
    <div className="narrative">
      <h3>Narrative</h3>
      <p>
        {narrative}
        {streaming && <span className="cursor" aria-hidden="true" />}
      </p>
    </div>
  );
}
