// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { clearRegistryForTest, listActions, invokeAction } from "./registry.js";
import { registerTabActions, restoreTabTitle, storedTabTitle, AGENT_TAB_MARK } from "./tab.js";

const ctx = { progress: () => {}, signal: new AbortController().signal };

describe("tab.title.set", () => {
  beforeEach(() => { clearRegistryForTest(); registerTabActions(); document.title = "host app"; });
  afterEach(() => { document.title = "host app"; });

  it("is a write action that stamps the robot mark in front of the title", async () => {
    expect(listActions().find((a) => a.name === "tab.title.set")?.kind).toBe("write");
    const res = await invokeAction("tab.title.set", { title: "Orders review" }, ctx);
    expect(res).toEqual({ title: `${AGENT_TAB_MARK} Orders review` });
    expect(document.title).toBe(`${AGENT_TAB_MARK} Orders review`);
  });

  it("does not double the mark when the agent already included it", async () => {
    await invokeAction("tab.title.set", { title: `${AGENT_TAB_MARK} already marked` }, ctx);
    expect(document.title).toBe(`${AGENT_TAB_MARK} already marked`);
  });

  it("trims and rejects a blank title", async () => {
    await invokeAction("tab.title.set", { title: "  spaced  " }, ctx);
    expect(document.title).toBe(`${AGENT_TAB_MARK} spaced`);
    await expect(invokeAction("tab.title.set", { title: "   " }, ctx)).rejects.toMatchObject({ code: "INVALID_ARGS" });
  });
});

describe("title persistence", () => {
  beforeEach(() => { clearRegistryForTest(); registerTabActions(); sessionStorage.clear(); document.title = "host app"; });

  it("remembers the stamped title in sessionStorage", async () => {
    await invokeAction("tab.title.set", { title: "Orders review" }, ctx);
    expect(storedTabTitle()).toBe(`${AGENT_TAB_MARK} Orders review`);
  });

  it("restoreTabTitle re-applies it after a reload and returns it", () => {
    sessionStorage.setItem("agent-ui-bridge.title", `${AGENT_TAB_MARK} Orders review`);
    expect(restoreTabTitle()).toBe(`${AGENT_TAB_MARK} Orders review`);
    expect(document.title).toBe(`${AGENT_TAB_MARK} Orders review`);
  });

  it("restoreTabTitle leaves an unnamed tab alone", () => {
    expect(restoreTabTitle()).toBeNull();
    expect(document.title).toBe("host app");
  });
});
