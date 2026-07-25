import { useState } from "react";
import "./App.css";
import { DraftVsBotApp } from "./components/DraftVsBotApp";
import { HomeScreen } from "./components/HomeScreen";
import { WorldsApp } from "./components/WorldsApp";

type AppMode = "home" | "draft" | "worlds";

function App() {
  const [mode, setMode] = useState<AppMode>("home");

  if (mode === "draft") {
    return <DraftVsBotApp onBack={() => setMode("home")} />;
  }

  if (mode === "worlds") {
    return <WorldsApp onBack={() => setMode("home")} />;
  }

  return (
    <HomeScreen
      onSelectDraft={() => setMode("draft")}
      onSelectWorlds={() => setMode("worlds")}
    />
  );
}

export default App;
