import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import App from "../App.vue";

describe("App", () => {
  it("renders the core pages and switches navigation", async () => {
    const wrapper = mount(App);

    expect(wrapper.text()).toContain("工作台");
    expect(wrapper.text()).toContain("上传发文");
    expect(wrapper.text()).toContain("文档画像");
    expect(wrapper.text()).toContain("字段定位");
    expect(wrapper.text()).toContain("影响分析");
    expect(wrapper.text()).toContain("工单草稿");

    await clickButton(wrapper, "上传发文");

    expect(wrapper.text()).toContain("上传监管发文");
    expect(wrapper.text()).toContain("指标变更扫描");
  });

  it("shows task workflow impact content", async () => {
    const wrapper = mount(App);

    await clickButton(wrapper, "影响分析");

    expect(wrapper.text()).toContain("影响分析");
    expect(wrapper.text()).toContain("1104");
    expect(wrapper.text()).toContain("开始影响分析");
    expect(wrapper.text()).not.toContain("影响主线 · 血缘穿透");
    expect(wrapper.text()).not.toContain("Hive / Airflow");
    expect(wrapper.text()).not.toContain("FTS · CRMS");
  });

  it("renders the five-step task workflow", async () => {
    const wrapper = mount(App);

    await clickButton(wrapper, "文档画像");

    expect(wrapper.text()).toContain("尚未生成文档画像");
    expect(wrapper.text()).toContain("开始扫描");
    expect(wrapper.text()).toContain("工单草稿");
  });
});

async function clickButton(wrapper: ReturnType<typeof mount>, label: string): Promise<void> {
  const button = wrapper.findAll("button").find((item) => item.text().includes(label));
  expect(button, `button ${label} should exist`).toBeTruthy();
  await button!.trigger("click");
}
