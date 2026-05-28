import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ExecutionPlanCard from "../ExecutionPlanCard.vue";
import {
  EXECUTION_PLAN_DEGRADED,
  EXECUTION_PLAN_HAPPY,
  EXECUTION_PLAN_NOT_GENERATED,
} from "@/fixtures/executionPlan";
import type { ExecutionPlanResponse } from "@/types/api";

const taskId = EXECUTION_PLAN_HAPPY.plan.task_id;
const staleResponse: ExecutionPlanResponse = {
  ...EXECUTION_PLAN_HAPPY,
  status: "STALE",
};
const readyNeedsReview: ExecutionPlanResponse = {
  ...EXECUTION_PLAN_HAPPY,
  plan: {
    ...EXECUTION_PLAN_HAPPY.plan,
    needs_human_review: true,
  },
};

function mockFetch(data: unknown, ok = true): ReturnType<typeof vi.fn> {
  return vi.fn(async () => ({
    ok,
    json: async () => data,
    text: async () => "network failed",
  })) as ReturnType<typeof vi.fn>;
}

function deferredJson(data: unknown) {
  let resolve!: () => void;
  const promise = new Promise<{ ok: true; json: () => Promise<unknown>; text: () => Promise<string> }>((done) => {
    resolve = () => done({
      ok: true,
      json: async () => data,
      text: async () => "",
    });
  });
  return { promise, resolve };
}

async function tick(): Promise<void> {
  await Promise.resolve();
}

describe("ExecutionPlanCard", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the not generated prompt and posts generation requests", async () => {
    const initialLoad = deferredJson(EXECUTION_PLAN_NOT_GENERATED);
    const generated = deferredJson(EXECUTION_PLAN_HAPPY);
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(initialLoad.promise)
      .mockReturnValueOnce(generated.promise);
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(ExecutionPlanCard, { props: { taskId } });
    await tick();
    expect(wrapper.find("[aria-label='执行规划加载中']").exists()).toBe(true);
    initialLoad.resolve();
    await flushPromises();

    expect(wrapper.text()).toContain("尚未生成执行规划");
    await wrapper.get("[data-test='execution-plan-generate']").trigger("click");
    expect(wrapper.find("[aria-label='执行规划更新中']").exists()).toBe(true);
    generated.resolve();
    await flushPromises();

    expect(fetchMock).toHaveBeenLastCalledWith(`/api/tasks/${taskId}/execution-plan`, expect.objectContaining({ method: "POST" }));
    expect(wrapper.text()).toContain("G24 同业融入口径调整");
  });

  it("renders ready plan sections and sends feedback to the feedback endpoint", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ok: true }),
      });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(ExecutionPlanCard, { props: { taskId, initial: readyNeedsReview } });
    await flushPromises();

    expect(wrapper.text()).toContain("执行阶段");
    expect(wrapper.findAll("[data-test='execution-phase']").length).toBe(3);
    expect(wrapper.findAll("[data-test='critical-risk']").length).toBe(2);
    expect(wrapper.text()).toContain("82%");
    expect(wrapper.text()).toContain("待人工复核");

    await wrapper.get("[data-test='feedback-up']").trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenCalledWith(
      `/api/tasks/${taskId}/execution-plan/feedback`,
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ thumbs: "up" }),
      }),
    );
    expect(wrapper.text()).toContain("已反馈");
  });

  it("renders degraded plans with warning and human review badge", async () => {
    vi.stubGlobal("fetch", mockFetch(EXECUTION_PLAN_DEGRADED));

    const wrapper = mount(ExecutionPlanCard, {
      props: { taskId, initial: EXECUTION_PLAN_DEGRADED },
    });
    await flushPromises();

    expect(wrapper.text()).toContain(EXECUTION_PLAN_DEGRADED.warning);
    expect(wrapper.text()).toContain("待人工复核");
    expect(wrapper.findAll("[data-test='execution-phase']").length).toBe(1);
  });

  it("renders stale plans with a stale banner", async () => {
    const wrapper = mount(ExecutionPlanCard, { props: { taskId, initial: staleResponse } });
    await flushPromises();

    expect(wrapper.text()).toContain("工单已更新，规划可能过时，建议重新生成");
    expect(wrapper.text()).toContain("重新生成");
  });

  it("shows a dismissible inline error while retaining the last good state", async () => {
    const changedTaskId = taskId + 1;
    const changedResponse = {
      ...EXECUTION_PLAN_HAPPY,
      plan: {
        ...EXECUTION_PLAN_HAPPY.plan,
        task_id: changedTaskId,
        executive_summary: "切换任务后的执行规划",
      },
    } satisfies ExecutionPlanResponse;
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("backend offline"))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => changedResponse,
        text: async () => "",
      });
    vi.stubGlobal("fetch", fetchMock);

    const wrapper = mount(ExecutionPlanCard, { props: { taskId, initial: EXECUTION_PLAN_HAPPY } });
    await wrapper.get("[data-test='execution-plan-regenerate']").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("backend offline");
    expect(wrapper.text()).toContain("G24 同业融入口径调整");

    await wrapper.get("[data-test='execution-plan-error-dismiss']").trigger("click");
    expect(wrapper.text()).not.toContain("backend offline");

    await wrapper.setProps({ taskId: changedTaskId, initial: null });
    await flushPromises();

    expect(fetchMock).toHaveBeenLastCalledWith(`/api/tasks/${changedTaskId}/execution-plan`, undefined);
    expect(wrapper.text()).toContain("切换任务后的执行规划");
  });
});
