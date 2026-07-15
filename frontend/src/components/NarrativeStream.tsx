import type { ReactNode } from "react";

interface NarrativeStreamProps {
  narrative: string;
  streaming: boolean;
}

type Block = { type: "paragraph"; text: string } | { type: "list"; items: string[] };

// The narrative comes from an LLM as loose markdown (bold + "- " bullets).
// No markdown library is wired up yet, so parse just enough of it here to
// stop **bold** and bullet lines from rendering as literal asterisks/dashes.
function parseBlocks(text: string): Block[] {
  const blocks: Block[] = [];
  let paragraphLines: string[] = [];
  let listItems: string[] = [];

  const flushParagraph = () => {
    if (paragraphLines.length) {
      blocks.push({ type: "paragraph", text: paragraphLines.join(" ").trim() });
      paragraphLines = [];
    }
  };
  const flushList = () => {
    if (listItems.length) {
      blocks.push({ type: "list", items: listItems });
      listItems = [];
    }
  };

  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }
    const bulletMatch = line.match(/^[-*]\s+(.*)/);
    if (bulletMatch) {
      flushParagraph();
      listItems.push(bulletMatch[1]);
    } else {
      flushList();
      paragraphLines.push(line);
    }
  }
  flushParagraph();
  flushList();
  return blocks;
}

function renderInline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={i}>{part.slice(2, -2)}</strong>
    ) : (
      part
    ),
  );
}

export function NarrativeStream({ narrative, streaming }: NarrativeStreamProps) {
  if (!narrative && !streaming) return null;

  const blocks = parseBlocks(narrative);

  return (
    <div className="narrative">
      <h3>Narrative</h3>
      <div className="narrative-body">
        {blocks.map((block, i) =>
          block.type === "list" ? (
            <ul key={i}>
              {block.items.map((item, j) => (
                <li key={j}>{renderInline(item)}</li>
              ))}
            </ul>
          ) : (
            <p key={i}>{renderInline(block.text)}</p>
          ),
        )}
        {streaming && <span className="cursor" aria-hidden="true" />}
      </div>
    </div>
  );
}
