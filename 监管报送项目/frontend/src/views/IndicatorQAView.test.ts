import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import IndicatorQAView from "./IndicatorQAView.vue";

describe("IndicatorQAView", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/indicator-qa/items") {
        return jsonResponse([
          { item_code: "G31.PART_I.1_0.C_修正久期", item_name: "修正久期" },
          { item_code: "G24.PART_II.5_0.B", item_name: "最大百家同业融入余额" },
        ]);
      }
      if (url.startsWith("/api/indicator-qa/ask/stream?")) {
        return new Response([
          'data: {"type":"meta","mode":"explanation","item_code":"G31.PART_I.1_0.C_修正久期","item_name":"修正久期","instruction_excerpts":[],"related_tickets":[]}',
          "",
          'data: {"type":"token","text":"修正久期用于衡量价格对收益率变化的敏感度。"}',
          "",
          'data: {"type":"keypoints","data":["组合指标按期末估值加权。"]}',
          "",
          'data: {"type":"done"}',
          "",
        ].join("\n"), {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        });
      }
      throw new Error(`unexpected url ${url}`);
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the immersive conversation workspace from the approved design", async () => {
    const wrapper = mount(IndicatorQAView);
    await flushPromises();

    expect(wrapper.get('[data-testid="qa-session-rail"]').text()).toContain("新建对话");
    expect(wrapper.get('[data-testid="qa-context-bar"]').text()).toContain("对话已锁定该指标上下文");
    expect(wrapper.get('[data-testid="qa-context-bar"]').text()).toContain("修正久期");
    expect(wrapper.get('[data-testid="qa-conversation"]').text()).toContain("G31 修正久期怎么计算？");
    expect(wrapper.get('[data-testid="qa-composer"]').text()).toContain("关联报表");
  });

  it("shows the empty-state examples after starting a new conversation", async () => {
    const wrapper = mount(IndicatorQAView);
    await wrapper.get('[data-testid="qa-new-chat"]').trigger("click");

    expect(wrapper.text()).toContain("问我任何报送指标的问题");
    expect(wrapper.text()).toContain("解释指标口径 · 排查数值异常 · 追溯血缘来源");
  });

  it("appends a streamed assistant response after sending a follow-up", async () => {
    const wrapper = mount(IndicatorQAView);
    await wrapper.get('[data-testid="qa-new-chat"]').trigger("click");
    await wrapper.get('[data-testid="qa-composer-input"]').setValue("解释一下修正久期");
    await wrapper.get('[data-testid="qa-send"]').trigger("click");
    await flushPromises();

    expect(wrapper.get('[data-testid="qa-conversation"]').text()).toContain("解释一下修正久期");
    expect(wrapper.get('[data-testid="qa-conversation"]').text()).toContain("修正久期用于衡量价格对收益率变化的敏感度。");
    expect(wrapper.get('[data-testid="qa-conversation"]').text()).toContain("组合指标按期末估值加权。");
  });
});

function jsonResponse(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
