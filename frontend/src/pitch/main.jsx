import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import Pitch from "./Pitch.jsx";
import "../styles.css";
import "./pitch.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <Pitch />
  </StrictMode>,
);
