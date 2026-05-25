import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "./client";

describe("api client", () => {
  it("loads the task workflow against the backend contract", async () => {
    const calls: Array<{ url: string; method?: string }> = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, method: init?.method });

      if (url.endsWith("/api/documents/upload")) {
        return jsonResponse({
          id: 7,
          title: "repo_notice",
          filename: "repo_notice.txt",
          content_type: "text/plain",
          storage_path: "/data/test_uploads/repo_notice.txt",
          text_excerpt: "excerpt",
          parsed_text: "full parsed text",
          status: "PARSED",
          parse_status: "PARSED",
          parser: "text",
          char_count: 6,
          paragraph_count: 1,
          table_count: 0,
          parse_quality: "LOW",
          parse_error_message: "",
          created_at: "2026-05-13T00:00:00Z",
        });
      }
      if (url.endsWith("/api/tasks/from-document/7")) {
        return jsonResponse({ id: 11, document_id: 7, title: "repo_notice规则加工任务", status: "CREATED", risk_level: "HIGH", created_at: "2026-05-13T00:00:00Z", updated_at: "2026-05-13T00:00:00Z" });
      }
      if (url.endsWith("/api/tasks/11/workflow")) {
        return jsonResponse({
          task: { id: 11, document_id: 7, title: "repo_notice规则加工任务", status: "IMPACT_ANALYZED", risk_level: "HIGH", created_at: "2026-05-13T00:00:00Z", updated_at: "2026-05-13T00:00:00Z" },
          document: {
            id: 7,
            title: "repo_notice",
            filename: "repo_notice.txt",
            content_type: "text/plain",
            storage_path: "/data/test_uploads/repo_notice.txt",
            text_excerpt: "excerpt",
            parsed_text: "full parsed text",
            status: "PARSED",
            parse_status: "PARSED",
            parser: "text",
            char_count: 6,
            paragraph_count: 1,
            table_count: 0,
            parse_quality: "LOW",
            parse_error_message: "",
            created_at: "2026-05-13T00:00:00Z",
          },
          document_profile: null,
          steps: [
            { code: "document", name: "上传发文", status: "DONE" },
            { code: "clauses", name: "条款证据", status: "DONE" },
            { code: "impact", name: "影响识别", status: "REVIEW_REQUIRED" },
            { code: "rule_cards", name: "规则卡片", status: "PENDING" },
            { code: "ticket", name: "工单草稿", status: "PENDING" },
          ],
          clauses: [{ id: 1, document_id: 7, clause_no: "一", clause_text: "公告原文", clause_level: 1, review_status: "PENDING", created_at: "2026-05-13T00:00:00Z" }],
          semantic_items: [{ id: 1, clause_id: 1, semantic_type: "SUBJECT", semantic_name: "适用主体", semantic_value: "境外机构投资者", evidence_text: "公告原文", confidence_score: 0.91, review_status: "PENDING" }],
          field_mappings: [],
          impact_items: [{ reporting_item_code: "G24.R03.C04", impact_type: "口径调整", impacted_reporting_field: "清算路径", impacted_source_fields: ["settlement_method"], impacted_lineage_roles: ["运营清算"], impact_reason: "DVP校验要求", recommended_action: "补充 DVP 校验", confidence_level: "HIGH", risk_level: "HIGH" }],
          rule_cards: [],
          ticket_drafts: [],
        });
      }
      if (url.endsWith("/api/documents/7/profile") && init?.method === "POST") {
        return jsonResponse({
          id: 1,
          document_id: 7,
          document_type: "业务通知",
          regulatory_topics: ["债券回购"],
          matched_business_objects: ["资金账户"],
          matched_terms: ["资金账户"],
          candidate_domains: ["数据治理"],
          candidate_impacts: ["账户一致性"],
          task_type: "BUSINESS_RULE_CHANGE",
          requires_business_object_match: true,
          data_governance_relevance: "RELEVANT",
          suggested_route: "FULL_ANALYSIS",
          should_create_task: true,
          confidence_score: 0.86,
          reason: "涉及账户管理",
          evidence_text: "资金收付应符合账户管理规定",
          llm_model: "fake",
          review_status: "PENDING",
          created_at: "2026-05-15T00:00:00Z",
        });
      }
      throw new Error(`unexpected url ${url}`);
    });

    const api = createApiClient("/api", fetchMock as typeof fetch);
    const document = await api.uploadDocument(new File(["notice"], "repo_notice.txt", { type: "text/plain" }));
    const task = await api.createTaskFromDocument(document.id);
    const workflow = await api.getTaskWorkflow(task.id);
    const profile = await api.profileDocument(document.id);

    expect(workflow.semantic_items[0].semantic_value).toBe("境外机构投资者");
    expect(profile.should_create_task).toBe(true);
    expect(workflow.impact_items[0].impacted_reporting_field).toBe("清算路径");
    expect(workflow.steps.map((step) => step.name)).toContain("影响识别");
    expect(calls.map((call) => `${call.method} ${call.url}`)).toEqual([
      "POST /api/documents/upload",
      "POST /api/tasks/from-document/7",
      "undefined /api/tasks/11/workflow",
      "POST /api/documents/7/profile",
    ]);
  });

  it("loads rule cards and concepts from the new backend contract", async () => {
    const calls: Array<{ url: string; method?: string }> = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      calls.push({ url, method: init?.method });

      if (url.includes("/api/rule-cards")) {
        return jsonResponse([
          {
            id: 1,
            card_code: "RC_G31_SCOPE_001",
            reporting_object_code: "G31",
            reporting_item_code: null,
            card_level: "L1",
            card_title: "G31 表统计范围",
            card_text: "本表统计范围不含表内自营投资中的股票投资",
            source_location: "G31 填报说明 §1.1",
            evidence_text: "本表统计范围",
            evidence_verified: true,
            confidence_level: "HIGH",
            review_status: "CONFIRMED",
            status: "ACTIVE",
            related_concept_codes: ["CON_BOND_INVESTMENT_BAL"],
          },
        ]);
      }
      if (url.endsWith("/api/concepts") || url.includes("/api/concepts?")) {
        return jsonResponse([
          {
            id: 1,
            concept_code: "CON_BOND_INVESTMENT_BAL",
            canonical_name: "债券投资余额",
            short_definition: "G31 债券投资账面余额",
            full_definition: "",
            concept_type: "METRIC",
            reporting_system_scope: "1104",
            current_version_no: 1,
            is_locked: false,
            status: "ACTIVE",
            aliases: ["债券投资余额", "债券投资账面余额"],
            related_reporting_item_codes: ["G31.PART_I.BOND_INVESTMENT_BALANCE"],
          },
        ]);
      }
      if (url.endsWith("/api/concepts/match")) {
        return jsonResponse({
          hits: [
            {
              concept_code: "CON_BOND_INVESTMENT_BAL",
              canonical_name: "债券投资余额",
              matched_alias: "债券投资余额",
              match_offset: 0,
              match_length: 5,
              related_reporting_item_codes: ["G31.PART_I.BOND_INVESTMENT_BALANCE"],
            },
          ],
        });
      }
      throw new Error(`unexpected url ${url}`);
    });

    const api = createApiClient("/api", fetchMock as typeof fetch);
    const cards = await api.listRuleCards({ reporting_object_code: "G31" });
    const concepts = await api.listConcepts();
    const hits = await api.matchConcepts("债券投资余额包含应收利息");

    expect(cards[0].card_code).toBe("RC_G31_SCOPE_001");
    expect(concepts[0].canonical_name).toBe("债券投资余额");
    expect(hits[0].matched_alias).toBe("债券投资余额");
  });
});

function jsonResponse(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}
