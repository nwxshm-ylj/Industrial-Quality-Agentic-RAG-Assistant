interface NavGlyphProps {
  children: string;
}

export function NavGlyph({ children }: NavGlyphProps) {
  return <span className="nav-glyph" aria-hidden="true">{children}</span>;
}
