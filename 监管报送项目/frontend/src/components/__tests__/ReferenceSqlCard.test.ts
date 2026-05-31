import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ReferenceSqlCard from "../ReferenceSqlCard.vue";
import {
  SQL_DEGRADED,
  SQL_NOT_APPLICABLE,
  SQL_NOT_GENERATED,
  SQL_READY,
} from "@/fixtures/referenceSql";

function mockFetch(data: unknown, ok = true): ReturnType<typeof vi.fn> {
  return vi.fn(async () => ({
    ok,
    json: async () => data,
    text: async () => "error",
  })) as ReturnType<typeof vi.fn>;
}

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch(SQL_NOT_GENERATED));
});
afterEach(() => {
  vi.restoreAllMocks();
});

// ── 6 态渲染 ────────────────────────────────────────────────────────────────

describe("NOT_GENERATED 态", () => {
  it("显示生成按钮，不显示 SQL", async () => {
    const wrapper = mount(ReferenceSqlCard, {
      props: { ticketId: 101, initial: SQL_NOT_GENERATED },
    });
    expect(wrapper.text()).toContain("AI 生成");
    expect(wrapper.find("[data-test='sql-display']").exists()).toBe(false);
  });
});

describe("READY 态", () => {
  it("显示 SQL 内容和置信度", async () => {
    const wrapper = mount(ReferenceSqlCard, {
      props: { ticketId: 102, initial: SQL_READY },
    });
    const pre = wrapper.find("[data-test='sql-display']");
    expect(pre.exists()).toBe(true);
    expect(pre.text()).toContain("SELECT");
    expect(wrapper.text()).toContain("87%");
  });

  it("显示 warnings，error 和 info 各一条", async () => {
    const wrapper = mount(ReferenceSqlCard, {
      props: { ticketId: 102, initial: SQL_READY },
    });
    expect(wrapper.find("[data-test='sql-warning-warning']").exists()).toBe(true);
    expect(wrapper.find("[data-test='sql-warning-info']").exists()).toBe(true);
  });

  it("显示安全警示横幅", async () => {
    const wrapper = mount(ReferenceSqlCard, {
      props: { ticketId: 102, initial: SQL_READY },
    });
    expect(wrapper.text()).toContain("必须人工审核");
  });
});

describe("NOT_APPLICABLE 态", () => {
  it("显示 not_applicable_reason，不显示编辑器和生成按钮", async () => {
    const wrapper = mount(ReferenceSqlCard, {
      props: { ticketId: 103, initial: SQL_NOT_APPLICABLE },
    });
    expect(wrapper.text()).toContain("口径确认");
    expect(wrapper.find("[data-test='sql-display']").exists()).toBe(false);
    expect(wrapper.find("[data-test='sql-editor']").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("AI 生成");
  });
});

describe("DEGRADED 态", () => {
  it("显示降级横幅和骨架 SQL", async () => {
    const wrapper = mount(ReferenceSqlCard, {
      props: { ticketId: 104, initial: SQL_DEGRADED },
    });
    expect(wrapper.text()).toContain("已降级");
    expect(wrapper.find("[data-test='sql-display']").text()).toContain("骨架模板");
  });

  it("显示 LLM_FAILED error warning", async () => {
    const wrapper = mount(ReferenceSqlCard, {
      props: { ticketId: 104, initial: SQL_DEGRADED },
    });
    expect(wrapper.find("[data-test='sql-warning-error']").exists()).toBe(true);
  });
});

// ── API 调用断言 ─────────────────────────────────────────────────────────────

describe("生成 POST", () => {
  it("点击「AI 生成」调用 POST /reference-sql/generate", async () => {
    const fetchMock = mockFetch(SQL_READY);
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("confirm", () => true);

    const wrapper = mount(ReferenceSqlCard, {
      props: { ticketId: 101, initial: SQL_NOT_GENERATED },
    });
    await wrapper.find("button").trigger("click");
    await flushPromises();

    const call = fetchMock.mock.calls.find((c) =>
      String(c[0]).includes("generate"),
    );
    expect(call).toBeTruthy();
    expect(call![1]).toMatchObject({ method: "POST" });
  });
});

describe("编辑 PUT", () => {
  it("点编辑→修改→保存，调用 PUT /reference-sql", async () => {
    const fetchMock = mockFetch({ ...SQL_READY, status: "EDITED_BY_USER", reference_sql: "SELECT 1" });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(ReferenceSqlCard, {
      props: { ticketId: 102, initial: SQL_READY },
    });

    const editBtn = wrapper.findAll("button").find((b) => b.text().includes("编辑"));
    await editBtn!.trigger("click");

    const textarea = wrapper.find("[data-test='sql-editor']");
    expect(textarea.exists()).toBe(true);
    await textarea.setValue("SELECT 1");

    const saveBtn = wrapper.findAll("button").find((b) => b.text().includes("保存"));
    await saveBtn!.trigger("click");
    await flushPromises();

    const putCall = fetchMock.mock.calls.find((c) => {
      const opts = c[1] as RequestInit | undefined;
      return opts?.method === "PUT";
    });
    expect(putCall).toBeTruthy();
    const body = JSON.parse(putCall![1]!.body as string);
    expect(body.reference_sql).toBe("SELECT 1");

    expect(wrapper.text()).toContain("已人工编辑");
  });
});

describe("反馈 POST", () => {
  it("点👍调用 POST /reference-sql/feedback，body 含 thumbs: up", async () => {
    const fetchMock = mockFetch({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(ReferenceSqlCard, {
      props: { ticketId: 102, initial: SQL_READY },
    });

    const upBtn = wrapper.findAll("button").find((b) => b.text().includes("👍"));
    await upBtn!.trigger("click");
    await flushPromises();

    const call = fetchMock.mock.calls.find((c) =>
      String(c[0]).includes("feedback"),
    );
    expect(call).toBeTruthy();
    const body = JSON.parse(call![1]!.body as string);
    expect(body.thumbs).toBe("up");
  });
});
