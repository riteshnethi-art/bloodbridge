import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge, Button, EmptyState, StatusPill } from "../components/ui";

describe("UI kit", () => {
  it("renders a button with loading state disabled", () => {
    render(<Button loading>Save</Button>);
    const btn = screen.getByRole("button", { name: /save/i });
    expect(btn).toBeDisabled();
  });

  it("renders status pills with humanized labels", () => {
    render(<StatusPill status="contact_initiated" />);
    expect(screen.getByText("contact initiated")).toBeInTheDocument();
  });

  it("renders badges and empty states", () => {
    render(
      <div>
        <Badge tone="red">demo partner</Badge>
        <EmptyState title="Nothing here" body="Try again later." />
      </div>,
    );
    expect(screen.getByText("demo partner")).toBeInTheDocument();
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
});
