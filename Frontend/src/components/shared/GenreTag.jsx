export default function GenreTag({ label, variant = "default" }) {
  const variants = {
    default: "bg-elevated border-border text-text-secondary hover:border-purple/50 hover:text-text-primary",
    purple:  "bg-purple/10 border-purple/30 text-purple",
    teal:    "bg-teal/10 border-teal/30 text-teal",
  };

  return (
    <span
      className={`inline-block text-2xs font-medium px-2 py-0.5 rounded-lg border transition-colors duration-150 ${variants[variant]}`}
    >
      {label}
    </span>
  );
}
