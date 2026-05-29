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
  it("switches from AI recommendation to business review tree", async () => {
    vi.stubGlobal("fetch", mockFetch());
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();

    expect(wrapper.text()).toContain("AI 推荐视图");
    expect(wrapper.text()).toContain("受影响字段");

    await wrapper.get("[data-test='business-review-tab']").trigger("click");

    expect(wrapper.text()).toContain("最大百家金融机构同业融入余额");
    expect(wrapper.text()).toContain("数据集市/ETL");
    expect(wrapper.text()).toContain("业务备注");
  });

  it("keeps required fields selected but allows optional fields to be unselected", async () => {
    vi.stubGlobal("fetch", mockFetch());
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();
    await wrapper.get("[data-test='business-review-tab']").trigger("click");

    const required = wrapper.get("[data-test='field-checkbox-rpt_g24.interbank_borrowing_bal_top100']");
    expect((required.element as HTMLInputElement).disabled).toBe(true);

    const optional = wrapper.get("[data-test='field-checkbox-interbank_deal.balance']");
    await optional.setValue(false);

    expect((optional.element as HTMLInputElement).checked).toBe(false);
  });

  it("adds a business field and saves reporting-item note", async () => {
    const fetchMock = mockFetch();
    vi.stubGlobal("fetch", fetchMock);
    const wrapper = mount(ImpactScopeReview, { props: { taskId: 101 } });
    await flushPromises();
    await wrapper.get("[data-test='business-review-tab']").trigger("click");

    await wrapper.get("[data-test='note-G24.MAIN.INTERBANK_BORROWING_BAL_TOP100']").setValue("历史数据由 ETL 团队补录。");
    await wrapper.get("[data-test='field-code-DATA_MART_ETL']").setValue("manual.etl_override_field");
    await wrapper.get("[data-test='field-name-DATA_MART_ETL']").setValue("业务补充字段");
    await wrapper.get("[data-test='add-field-DATA_MART_ETL']").trigger("click");
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
    await wrapper.get("[data-test='business-review-tab']").trigger("click");
    await wrapper.get("[data-test='confirm-impact-review']").trigger("click");
    await flushPromises();

    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/tasks/101/impact-review/confirm",
      expect.objectContaining({ method: "POST" }),
    );
    expect(wrapper.emitted("confirmed")).toHaveLength(1);
  });
});
