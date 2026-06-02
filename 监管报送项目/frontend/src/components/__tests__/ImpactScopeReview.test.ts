import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

import ImpactScopeReview from "../ImpactScopeReview.vue";
import { IMPACT_REVIEW_RESPONSE } from "@/fixtures/impactReview";

function mockFetch(data: unknown = IMPACT_REVIEW_RESPONSE) {
  return vi.fn(async () => ({
    ok: true,
    json: async () => data,
    text: async () => "",
  })) as ReturnType<typeof vi.fn>;
}

describe("ImpactScopeReview", () => {
  it("shows the business review tree directly without the AI recommendation view", async () => {
    vi.stubGlobal("fetch", mockFetch());
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();

    expect(wrapper.text()).not.toContain("AI 推荐视图");
    expect(wrapper.find("[data-test='business-review-tab']").exists()).toBe(false);
    expect(wrapper.text()).toContain("最大百家金融机构同业融入余额");
    // 按真实 system_name 展示，而不是抽象团队角色名（旧版本是"数据集市/ETL"）
    expect(wrapper.text()).toContain("监管报送系统");
    expect(wrapper.text()).toContain("同业业务系统");
    expect(wrapper.text()).toContain("业务备注");
  });

  it("keeps required fields selected but allows optional fields to be unselected", async () => {
    vi.stubGlobal("fetch", mockFetch());
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();

    const required = wrapper.get("[data-test='field-checkbox-rpt_g24.interbank_borrowing_bal_top100']");
    expect((required.element as HTMLInputElement).disabled).toBe(true);

    const optional = wrapper.get("[data-test='field-checkbox-interbank_deal.balance']");
    await optional.setValue(false);

    expect((optional.element as HTMLInputElement).checked).toBe(false);
  });

  it("emits stage change when clicking split-ticket step", async () => {
    vi.stubGlobal("fetch", mockFetch());
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();

    await wrapper.get("[data-test='review-stage-3']").trigger("click");

    expect(wrapper.emitted("stage-change")).toEqual([[3]]);
  });

  it("adds a business field and saves reporting-item note", async () => {
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();

    await wrapper.get("[data-test='note-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").setValue("历史数据由 ETL 团队补录。");
    // 业务追加字段挂在真实系统桶里（RPT 报送集市），不再用抽象的 DATA_MART_ETL
    await wrapper.get("[data-test='field-code-RPT']").setValue("manual.etl_override_field");
    await wrapper.get("[data-test='field-name-RPT']").setValue("业务补充字段");
    await wrapper.get("[data-test='add-field-RPT']").trigger("click");
    await wrapper.get("[data-test='save-impact-review']").trigger("click");
    await flushPromises();

    const saveCall = fetchMock.mock.calls.find((call) => call[1]?.method === "PUT");
    expect(saveCall?.[1]).toMatchObject({ method: "PUT" });
    expect(String(saveCall?.[1]?.body)).toContain("manual.etl_override_field");
    expect(String(saveCall?.[1]?.body)).toContain("历史数据由 ETL 团队补录");
  });

  it("confirms review and emits confirmed event", async () => {
    const fetchMock = mockFetch({ parent: {}, children: [] });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => IMPACT_REVIEW_RESPONSE,
      text: async () => "",
    });
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();
    await wrapper.get("[data-test='confirm-impact-review']").trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/tasks/101/impact-review/confirm",
      expect.objectContaining({ method: "POST" }),
    );
    expect(wrapper.emitted("confirmed")).toHaveLength(1);
  });

  it("commits a pending field draft before confirming the review", async () => {
    const fetchMock = mockFetch({ parent: {}, children: [] });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => IMPACT_REVIEW_RESPONSE,
      text: async () => "",
    });
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();

    await wrapper.get("[data-test='field-code-INTERBANK_CORE']").setValue("interbank_deal.pending_override");
    await wrapper.get("[data-test='field-name-INTERBANK_CORE']").setValue("待自动提交字段");
    await wrapper.get("[data-test='confirm-impact-review']").trigger("click");
    await flushPromises();

    const confirmCall = fetchMock.mock.calls.find((call) => String(call[0]).endsWith("/impact-review/confirm"));
    expect(String(confirmCall?.[1]?.body)).toContain("interbank_deal.pending_override");
    expect(String(confirmCall?.[1]?.body)).toContain("待自动提交字段");
  });

  it("adds a new system field from a catalog option", async () => {
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();

    await wrapper.get("[data-test='new-system-option-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").setValue("VALUATION");
    await wrapper.get("[data-test='new-system-field-code-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").setValue("valuation_bond_metric.modified_duration");
    await wrapper.get("[data-test='new-system-field-name-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").setValue("债券修正久期");
    await wrapper.get("[data-test='add-system-field-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").trigger("click");
    await wrapper.get("[data-test='save-impact-review']").trigger("click");
    await flushPromises();

    const saveCall = fetchMock.mock.calls.find((call) => call[1]?.method === "PUT");
    expect(String(saveCall?.[1]?.body)).toContain('"responsible_system":"VALUATION"');
    expect(String(saveCall?.[1]?.body)).toContain('"responsible_system_zh":"估值计量系统"');
    expect(String(saveCall?.[1]?.body)).toContain("valuation_bond_metric.modified_duration");
  });

  it("commits a manually entered new system and field before confirming", async () => {
    const fetchMock = mockFetch({ parent: {}, children: [] });
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => IMPACT_REVIEW_RESPONSE,
      text: async () => "",
    });
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();

    await wrapper.get("[data-test='new-system-code-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").setValue("MANUAL_CORE");
    await wrapper.get("[data-test='new-system-name-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").setValue("手工补录系统");
    await wrapper.get("[data-test='new-system-type-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").setValue("SOURCE");
    await wrapper.get("[data-test='new-system-field-code-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").setValue("manual_core.extra_field");
    await wrapper.get("[data-test='new-system-field-name-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").setValue("手工补录字段");
    await wrapper.get("[data-test='confirm-impact-review']").trigger("click");
    await flushPromises();

    const confirmCall = fetchMock.mock.calls.find((call) => String(call[0]).endsWith("/impact-review/confirm"));
    expect(String(confirmCall?.[1]?.body)).toContain('"responsible_system":"MANUAL_CORE"');
    expect(String(confirmCall?.[1]?.body)).toContain('"responsible_system_zh":"手工补录系统"');
    expect(String(confirmCall?.[1]?.body)).toContain("manual_core.extra_field");
  });
});
