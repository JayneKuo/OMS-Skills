from __future__ import annotations

import hashlib
import json


DEFAULT_SHOPIFY_API_VERSION = "2026-01"


def _normalize_channel(value):
    return str(value).strip().upper() if value is not None else ""


def _errors_for_channel(channel_summary, channel_code):
    normalized_channel_code = _normalize_channel(channel_code)
    summary = next(
        (item for item in channel_summary if _normalize_channel(item.get("channel_code")) == normalized_channel_code),
        {},
    )
    return summary.get("errors") or []


def _normalized(value):
    return str(value).strip().lower() if value is not None else ""


def _is_submit_allowed(channel_product, warnings):
    if not channel_product.get("channel_product_id"):
        return False

    retry_listing_statuses = {"failed", "fail", "error", "rejected", "draft", "publish_failed"}
    retry_audit_statuses = {"rejected", "failed", "draft"}
    status_fields = ("listing_status", "status", "publish_status")

    return any([
        bool(channel_product.get("last_error")),
        bool(warnings),
        any(_normalized(channel_product.get(field)) in retry_listing_statuses for field in status_fields),
        _normalized(channel_product.get("audit_status")) in retry_audit_statuses,
        channel_product.get("publish_success") is False,
    ])


CHANNEL_PRODUCT_BUSINESS_FIELDS = (
    "publishStatus",
    "publish_status",
    "listing_status",
    "listingStatus",
    "audit_status",
    "auditStatus",
    "sync_status",
    "syncStatus",
    "status",
)
PUBLISH_HISTORY_BUSINESS_FIELDS = ("status", "id", "error")


def _response_data(response, default):
    if not isinstance(response, dict):
        return default
    return response.get("data", default)


def _extract_channel_product_data(response):
    if not isinstance(response, dict):
        return {}
    data = response.get("data")
    if isinstance(data, dict):
        return data
    return response


def _first_present(mapping, keys):
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


def _channel_product_id(channel_product):
    return _first_present(channel_product, ("channel_product_id", "channelProductId", "id"))


def _live_submit_warnings(channel_product):
    warnings = []
    for field in ("last_error", "lastError", "errorMessage"):
        value = channel_product.get(field)
        if value and value not in warnings:
            warnings.append(value)

    validation_errors = channel_product.get("validation_errors")
    if validation_errors is None:
        validation_errors = channel_product.get("validationErrors")
    if isinstance(validation_errors, list):
        for error in validation_errors:
            if error and error not in warnings:
                warnings.append(error)
    elif validation_errors and validation_errors not in warnings:
        warnings.append(validation_errors)

    return warnings


def _live_submit_candidate(channel_product):
    return {
        "channel_product_id": _channel_product_id(channel_product),
        "last_error": _first_present(channel_product, ("last_error", "lastError", "errorMessage")),
        "listing_status": _first_present(channel_product, ("listing_status", "listingStatus")),
        "status": channel_product.get("status"),
        "publish_status": _first_present(channel_product, ("publish_status", "publishStatus")),
        "audit_status": _first_present(channel_product, ("audit_status", "auditStatus")),
        "publish_success": _first_present(channel_product, ("publish_success", "publishSuccess")),
    }


def _extract_channel_product_business_fields(response):
    data = _response_data(response, {})
    if not isinstance(data, dict):
        return {}
    return {field: data.get(field) for field in CHANNEL_PRODUCT_BUSINESS_FIELDS if field in data}


def _extract_publish_history_business_records(response):
    data = _response_data(response, [])
    if isinstance(data, dict):
        records = data.get("records") or data.get("list") or data.get("items") or []
    elif isinstance(data, list):
        records = data
    else:
        records = []

    business_records = []
    for item in records:
        if not isinstance(item, dict):
            continue
        business_records.append({field: item.get(field) for field in PUBLISH_HISTORY_BUSINESS_FIELDS if field in item})
    return business_records


def _execution_form_token(merchant_no, identifier, action, targets):
    allowed_channel_product_ids = sorted(
        str(target.get("channel_product_id"))
        for target in targets
        if isinstance(target, dict) and target.get("allowed") is True and target.get("channel_product_id")
    )
    token_payload = {
        "merchant_no": merchant_no,
        "identifier": identifier,
        "action": action,
        "allowed_channel_product_ids": allowed_channel_product_ids,
    }
    return hashlib.sha256(
        json.dumps(token_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _oms_shopify_publish_form_token(merchant_no, identifier, request_payload):
    token_payload = {
        "merchant_no": merchant_no,
        "identifier": identifier,
        "action": "oms_shopify_publish",
        "request_payload": request_payload,
    }
    return hashlib.sha256(
        json.dumps(token_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()



def _direct_shopify_form_token(merchant_no, identifier, action, shop_domain, api_version, product_payload):
    token_payload = {
        "merchant_no": merchant_no,
        "identifier": identifier,
        "action": action,
        "shop_domain": shop_domain,
        "api_version": api_version,
        "product_payload": product_payload,
    }
    return hashlib.sha256(
        json.dumps(token_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()



def _build_shopify_product_payload(details: dict, requested_status: str | None = None) -> dict:
    product = details.get("product") or {}
    skus = details.get("skus") or []
    status = str(requested_status or "DRAFT").upper()
    payload = {
        "title": product.get("title") or product.get("name") or "Untitled product",
        "vendor": product.get("brand") or "",
        "productType": product.get("category") or "",
        "status": status if status in {"DRAFT", "ACTIVE"} else "DRAFT",
        "variants": [],
    }
    for sku in skus:
        variant = {"sku": sku.get("seller_sku") or sku.get("sku") or sku.get("internal_sku_id")}
        if sku.get("price") not in (None, ""):
            variant["price"] = str(sku["price"])
        payload["variants"].append({key: value for key, value in variant.items() if value not in (None, "")})
    if not payload["variants"] and product.get("price") not in (None, ""):
        payload["variants"].append({"price": str(product["price"])})
    return payload


def _build_direct_shopify_form(identifier, merchant_no, filters: dict, details: dict) -> dict:
    shop_domain = filters.get("shop_domain")
    admin_access_token = filters.get("admin_access_token")
    api_version = filters.get("api_version") or DEFAULT_SHOPIFY_API_VERSION
    missing_auth_fields = []
    if not shop_domain:
        missing_auth_fields.append("shop_domain")
    if not admin_access_token:
        missing_auth_fields.append("admin_access_token")
    product_payload = _build_shopify_product_payload(details, filters.get("shopify_status"))
    targets = [{
        "shop_domain": shop_domain,
        "api_version": api_version,
        "allowed": not missing_auth_fields,
        "product_payload": product_payload,
    }]
    return {
        "requires_confirmation": True,
        "next_action": "collect_auth_and_user_decision" if missing_auth_fields else "collect_user_decision",
        "action": "direct_shopify_product_create",
        "merchant_no": merchant_no,
        "identifier": identifier,
        "shop_domain": shop_domain,
        "api_version": api_version,
        "missing_auth_fields": missing_auth_fields,
        "contains_secret": False,
        "product_payload": product_payload,
        "targets": targets,
        "form_token": _direct_shopify_form_token(
            merchant_no,
            identifier,
            "direct_shopify_product_create",
            shop_domain,
            api_version,
            product_payload,
        ),
    }


def _build_execution_form(action, merchant_no, identifier, target_channels, details):
    if action != "submit_existing_channel_product":
        return None

    channel_products = details.get("channel_products") or []
    channel_summary = details.get("channel_summary") or []
    targets = []

    normalized_target_channels = {_normalize_channel(channel) for channel in target_channels}

    for channel_product in channel_products:
        channel_code = channel_product.get("channel_code")
        if normalized_target_channels and _normalize_channel(channel_code) not in normalized_target_channels:
            continue

        warnings = []
        last_error = channel_product.get("last_error")
        if last_error:
            warnings.append(last_error)
        for error in _errors_for_channel(channel_summary, channel_code):
            if error not in warnings:
                warnings.append(error)

        channel_product_id = channel_product.get("channel_product_id")
        targets.append({
            "channel_product_id": channel_product_id,
            "channel_code": channel_code,
            "current_listing_status": channel_product.get("listing_status"),
            "current_audit_status": channel_product.get("audit_status"),
            "allowed": _is_submit_allowed(channel_product, warnings),
            "warnings": warnings,
        })

    return {
        "requires_confirmation": True,
        "next_action": "collect_user_decision",
        "action": action,
        "merchant_no": merchant_no,
        "identifier": identifier,
        "targets": targets,
        "form_token": _execution_form_token(merchant_no, identifier, action, targets),
    }


class ProductListingPlannerEngine:
    def __init__(self, execution_adapter=None):
        self._execution_adapter = execution_adapter

    def build_oms_shopify_publish_form(self, identifier=None, merchant_no=None, request_payload=None):
        request_payload = request_payload or {}
        return {
            "requires_confirmation": True,
            "next_action": "collect_user_decision",
            "action": "oms_shopify_publish",
            "merchant_no": merchant_no,
            "identifier": identifier,
            "request_payload": request_payload,
            "targets": request_payload.get("channels") or [],
            "form_token": _oms_shopify_publish_form_token(merchant_no, identifier, request_payload),
        }

    def execute(self, request=None):
        request = request or {}
        if request.get("confirmed") is not True:
            return {
                "success": False,
                "summary": "缺少用户确认，未执行发布提交。",
                "final_conclusion": "Execution failed",
                "errors": ["confirmation_required"],
            }
        if not self._execution_adapter:
            return {
                "success": False,
                "summary": "缺少 OMS 执行适配器，无法提交发布。",
                "final_conclusion": "Execution failed",
                "errors": ["missing_execution_adapter"],
            }

        action = request.get("action")
        if action == "direct_shopify_product_create":
            return self._execute_direct_shopify_product_create(request)
        if action == "oms_shopify_publish":
            return self._execute_oms_shopify_publish(request)
        if action != "submit_existing_channel_product":
            return {
                "success": False,
                "summary": "当前不支持该发布动作。",
                "final_conclusion": "Execution failed",
                "errors": ["unsupported_action"],
            }

        targets = request.get("targets")
        if targets is None or targets == []:
            return {
                "success": False,
                "summary": "缺少执行目标，未提交发布。",
                "final_conclusion": "Execution failed",
                "errors": ["missing_targets"],
            }
        if not isinstance(targets, list) or not all(isinstance(target, dict) for target in targets):
            return {
                "success": False,
                "summary": "执行目标格式无效，未提交发布。",
                "final_conclusion": "Execution failed",
                "errors": ["invalid_targets"],
            }

        expected_form_token = _execution_form_token(
            request.get("merchant_no"),
            request.get("identifier"),
            request.get("action"),
            targets,
        )
        if request.get("form_token") != expected_form_token:
            return {
                "success": False,
                "summary": "执行表单校验失败，未提交发布。",
                "final_conclusion": "Execution failed",
                "errors": ["invalid_execution_form"],
            }

        executions = []
        verification = []
        api_failed = False
        changed = False

        for target in targets:
            channel_product_id = target.get("channel_product_id")
            if target.get("allowed") is not True:
                api_failed = True
                executions.append({
                    "channel_product_id": channel_product_id,
                    "endpoint": "/rpc-api/channel-product/submit",
                    "request_payload": {},
                    "raw_response": None,
                    "error": "disallowed_target",
                })
                continue
            if not channel_product_id:
                api_failed = True
                executions.append({
                    "channel_product_id": None,
                    "endpoint": "/rpc-api/channel-product/submit",
                    "request_payload": {},
                    "raw_response": None,
                    "error": "missing_channel_product_id",
                })
                continue

            before_product = self._execution_adapter.get_channel_product(channel_product_id)
            live_channel_product = _extract_channel_product_data(before_product)
            live_merchant_no = _first_present(live_channel_product, ("merchantNo", "merchant_no"))
            if request.get("merchant_no") and live_merchant_no and str(request.get("merchant_no")) != str(live_merchant_no):
                api_failed = True
                executions.append({
                    "channel_product_id": channel_product_id,
                    "endpoint": "/rpc-api/channel-product/submit",
                    "request_payload": {},
                    "raw_response": None,
                    "error": "merchant_mismatch",
                })
                continue

            live_warnings = _live_submit_warnings(live_channel_product)
            if not _is_submit_allowed(_live_submit_candidate(live_channel_product), live_warnings):
                api_failed = True
                executions.append({
                    "channel_product_id": channel_product_id,
                    "endpoint": "/rpc-api/channel-product/submit",
                    "request_payload": {},
                    "raw_response": None,
                    "error": "live_target_not_allowed",
                })
                continue

            before_history = self._execution_adapter.list_publish_history_by_channel_product(channel_product_id)
            payload = {"id": channel_product_id, "channelProductId": channel_product_id}
            raw_response = self._execution_adapter.submit_channel_product(payload)
            after_product = self._execution_adapter.get_channel_product(channel_product_id)
            after_history = self._execution_adapter.list_publish_history_by_channel_product(channel_product_id)
            response_success = isinstance(raw_response, dict) and raw_response.get("code") in (0, 200, "0", "200")
            if not response_success:
                api_failed = True

            business_result_changed = self._business_result_changed(
                before_product,
                after_product,
                before_history,
                after_history,
            )
            changed = changed or business_result_changed
            executions.append({
                "channel_product_id": channel_product_id,
                "endpoint": "/rpc-api/channel-product/submit",
                "request_payload": payload,
                "raw_response": raw_response,
            })
            verification.append({
                "channel_product_id": channel_product_id,
                "before_channel_product": before_product,
                "after_channel_product": after_product,
                "before_publish_history": before_history,
                "after_publish_history": after_history,
                "business_result_changed": business_result_changed,
            })

        final_conclusion = self._final_conclusion(api_failed, changed)
        execution_errors = [execution["error"] for execution in executions if execution.get("error")]
        if final_conclusion == "Execution failed" and not execution_errors:
            execution_errors = ["submit_failed"]
        return {
            "success": final_conclusion != "Execution failed",
            "summary": self._execution_summary(final_conclusion),
            "final_conclusion": final_conclusion,
            "details": {"executions": executions, "verification": verification},
            "errors": [] if final_conclusion != "Execution failed" else execution_errors,
        }

    def _execute_direct_shopify_product_create(self, request):
        expected_form_token = _direct_shopify_form_token(
            request.get("merchant_no"),
            request.get("identifier"),
            request.get("action"),
            request.get("shop_domain"),
            request.get("api_version"),
            request.get("product_payload"),
        )
        if request.get("form_token") != expected_form_token:
            return {
                "success": False,
                "summary": "执行表单校验失败，未提交发布。",
                "final_conclusion": "Execution failed",
                "errors": ["invalid_execution_form"],
            }
        if not request.get("admin_access_token"):
            return {
                "success": False,
                "summary": "缺少 Shopify 授权信息，未提交发布。",
                "final_conclusion": "Execution failed",
                "errors": ["missing_admin_access_token"],
            }

        create_response = self._execution_adapter.create_shopify_product(
            request.get("shop_domain"),
            request.get("api_version"),
            request.get("admin_access_token"),
            request.get("product_payload"),
        )
        created_product = self._shopify_product_from_response(create_response)
        product_id = created_product.get("id")
        if not product_id:
            return {
                "success": False,
                "summary": "Shopify 商品创建失败。",
                "final_conclusion": "Execution failed",
                "details": {"executions": [{"raw_response": create_response}]},
                "errors": ["missing_shopify_product_id"],
            }

        readback_response = self._execution_adapter.get_shopify_product(
            request.get("shop_domain"),
            request.get("api_version"),
            request.get("admin_access_token"),
            product_id,
        )
        readback_product = self._shopify_product_from_response(readback_response)
        changed = self._shopify_product_matches(request.get("product_payload") or {}, product_id, readback_product)
        final_conclusion = self._final_conclusion(False, changed)
        return {
            "success": True,
            "summary": self._execution_summary(final_conclusion),
            "final_conclusion": final_conclusion,
            "details": {
                "executions": [{"shop_domain": request.get("shop_domain"), "product_id": product_id}],
                "verification": {"product_id": product_id, "business_result_changed": changed},
            },
            "errors": [],
        }

    def _execute_oms_shopify_publish(self, request):
        expected_form_token = _oms_shopify_publish_form_token(
            request.get("merchant_no"),
            request.get("identifier"),
            request.get("request_payload"),
        )
        if request.get("form_token") != expected_form_token:
            return {
                "success": False,
                "summary": "执行表单校验失败，未提交发布。",
                "final_conclusion": "Execution failed",
                "errors": ["invalid_execution_form"],
            }

        publish_result = self._execution_adapter.publish_oms_shopify_product(
            request.get("merchant_no"),
            request.get("request_payload") or {},
        )
        changed = self._oms_publish_result_changed(publish_result)
        final_conclusion = self._final_conclusion(not publish_result.get("success"), changed)
        return {
            "success": final_conclusion != "Execution failed",
            "summary": self._execution_summary(final_conclusion),
            "final_conclusion": final_conclusion,
            "details": {"executions": [publish_result], "verification": {"business_result_changed": changed}},
            "errors": [] if final_conclusion != "Execution failed" else publish_result.get("errors", ["oms_shopify_publish_failed"]),
        }

    @staticmethod
    def _shopify_product_from_response(response):
        if not isinstance(response, dict):
            return {}
        product = response.get("product")
        if isinstance(product, dict):
            return product
        data = response.get("data")
        if isinstance(data, dict) and isinstance(data.get("product"), dict):
            return data["product"]
        return {}

    @staticmethod
    def _shopify_product_matches(product_payload, product_id, readback_product):
        if not readback_product or str(readback_product.get("id")) != str(product_id):
            return False
        if product_payload.get("title") and readback_product.get("title") != product_payload.get("title"):
            return False
        if product_payload.get("status") and _normalize_channel(readback_product.get("status")) != _normalize_channel(product_payload.get("status")):
            return False
        expected_skus = {variant.get("sku") for variant in product_payload.get("variants", []) if variant.get("sku")}
        readback_skus = {variant.get("sku") for variant in readback_product.get("variants", []) if isinstance(variant, dict) and variant.get("sku")}
        return not expected_skus or expected_skus.issubset(readback_skus)

    @staticmethod
    def _oms_publish_result_changed(publish_result):
        if not isinstance(publish_result, dict):
            return False
        details = publish_result.get("details") or {}
        channel_sync = details.get("channel_sync") or {}
        data = channel_sync.get("data") if isinstance(channel_sync, dict) else {}
        if not isinstance(data, dict):
            return False
        if data.get("successCount", 0):
            return True
        return bool(data.get("successList"))

    @staticmethod
    def _business_result_changed(before_product, after_product, before_history, after_history):
        before_product_fields = _extract_channel_product_business_fields(before_product)
        after_product_fields = _extract_channel_product_business_fields(after_product)
        if before_product_fields != after_product_fields:
            return True

        before_history_records = _extract_publish_history_business_records(before_history)
        after_history_records = _extract_publish_history_business_records(after_history)
        if before_history_records != after_history_records:
            return True

        if any(
            _normalize_channel(after_product_fields.get(field)) == "PUBLISHING"
            for field in ("publishStatus", "publish_status")
        ):
            return True

        return any(_normalize_channel(item.get("status")) == "PUBLISHING" for item in after_history_records)

    @staticmethod
    def _final_conclusion(api_failed, changed):
        if api_failed:
            return "Execution failed"
        if changed:
            return "Executed successfully"
        return "Submitted successfully but business result did not take effect"

    @staticmethod
    def _execution_summary(final_conclusion):
        if final_conclusion == "Executed successfully":
            return "发布提交已执行，回查显示业务状态或发布历史发生变化。"
        if final_conclusion == "Submitted successfully but business result did not take effect":
            return "接口已接受发布提交，但回查未发现渠道商品或发布历史变化。"
        return "发布提交失败。"

    def plan(self, identifier=None, merchant_no=None, intent=None, filters=None, context=None):
        filters = filters or {}
        context = context or {}
        product_query_result = context.get("product_query_result") or {}
        if not product_query_result:
            return {
                "success": True,
                "summary": "缺少商品事实查询结果，需先执行 product-query。",
                "reason": "规划依赖商品主档、SKU、渠道状态和发布历史。",
                "evidences": [],
                "confidence": "low",
                "data_completeness": "insufficient",
                "severity": None,
                "recommendations": [
                    {
                        "action": "run_product_query_first",
                        "precondition": "提供商品标识和商户号",
                        "risk": "缺少事实数据会导致上架规划不可靠",
                        "priority": "high",
                        "expected_effect": "获得可用于规划的商品事实包",
                    }
                ],
                "metrics": {"target_channel_count": len(filters.get("target_channels") or [])},
                "details": {
                    "channel_priority": [],
                    "readiness_checklist": [
                        {
                            "item": "商品事实查询",
                            "status": "blocked",
                            "evidence": "缺少 product_query_result，无法确认商品主档、SKU、渠道状态和发布历史。",
                        }
                    ],
                    "content_plan": {},
                    "image_plan": {},
                    "launch_steps": [
                        {
                            "step": 1,
                            "title": "先查询商品事实",
                            "actions": ["运行 product-query 获取商品主档、SKU、渠道商品和发布历史"],
                            "owner": "Product Agent",
                            "priority": "P0",
                        }
                    ],
                    "risks": ["缺少 product_query_result"],
                },
                "charts": [],
                "visual_blocks": [],
                "links": [],
                "errors": [],
            }

        details = product_query_result.get("details") or {}
        channel_summary = details.get("channel_summary") or []
        diagnosis_result = context.get("product_diagnosis_result") or {}
        target_channels = filters.get("target_channels") or [item.get("channel_code") for item in channel_summary]
        channel_priority = []

        diagnosis_issues = (diagnosis_result.get("details") or {}).get("blocking_issues") or []
        diagnosis_issue_codes = {issue.get("code") for issue in diagnosis_issues}

        for channel in target_channels:
            normalized_channel = _normalize_channel(channel)
            summary = next(
                (item for item in channel_summary if _normalize_channel(item.get("channel_code")) == normalized_channel),
                {},
            )
            errors = summary.get("errors") or []
            if normalized_channel == "SHOPIFYV3" and "unsupported_oms_shopify_channel_type" in diagnosis_issue_codes:
                channel_priority.append({
                    "channel_code": channel,
                    "priority": "P0",
                    "status": "blocked",
                    "reason": "当前 OMS 发布服务对 ShopifyV3 的底层 channel type 支持存在问题。",
                    "required_actions": ["确认 ShopifyV3 渠道配置与发布服务支持关系"],
                    "risks": ["继续使用 ShopifyV3 会重复发布失败"],
                })
            elif normalized_channel == "SHEIN" and errors:
                channel_priority.append({
                    "channel_code": channel,
                    "priority": "P1",
                    "status": "blocked",
                    "reason": "SHEIN 渠道存在商品属性/SKC/销售属性缺失错误。",
                    "required_actions": ["补齐 SKC", "补齐销售属性", "补齐商品属性"],
                    "risks": ["未补齐前重新发布会继续失败"],
                })
            elif errors:
                channel_priority.append({
                    "channel_code": channel,
                    "priority": "P1",
                    "status": "blocked",
                    "reason": "该渠道存在发布错误，需要先处理错误后再提交发布。",
                    "required_actions": ["查看渠道发布错误并修复源商品或渠道资料"],
                    "risks": ["未修复前重新发布可能继续失败"],
                })
            else:
                channel_priority.append({
                    "channel_code": channel,
                    "priority": "P2",
                    "status": "ready",
                    "reason": "当前事实数据未发现该渠道阻塞项。",
                    "required_actions": [],
                    "risks": [],
                })

        channel_priority.sort(key=lambda item: item["priority"])
        blocked_count = sum(1 for item in channel_priority if item["status"] == "blocked")
        ready_count = sum(1 for item in channel_priority if item["status"] == "ready")
        action = filters.get("action") or "submit_existing_channel_product"
        if action == "direct_shopify_product_create":
            execution_form = _build_direct_shopify_form(identifier, merchant_no, filters, details)
        else:
            execution_form = _build_execution_form(
                action,
                merchant_no,
                identifier,
                target_channels,
                details,
            )
        execution_allowed = bool(
            execution_form and any(target.get("allowed") for target in execution_form["targets"])
        )

        product = details.get("product") or {}
        skus = details.get("skus") or []
        readiness_checklist = [
            {
                "item": "商品标题",
                "status": "ready" if product.get("title") else "blocked",
                "evidence": product.get("title") or "缺少商品标题",
            },
            {
                "item": "SKU",
                "status": "ready" if skus else "blocked",
                "evidence": f"{len(skus)} 个 SKU 可用" if skus else "缺少 SKU",
            },
            {
                "item": "价格",
                "status": "ready" if product.get("price") and product.get("currency") else "blocked",
                "evidence": (
                    f"{product.get('currency')} {product.get('price')}"
                    if product.get("price") and product.get("currency")
                    else "缺少价格或币种"
                ),
            },
            {
                "item": "图片",
                "status": "ready" if product.get("image_count") else "blocked",
                "evidence": f"{product.get('image_count')} 张图片" if product.get("image_count") else "缺少商品图片",
            },
        ]
        if any(_normalize_channel(item["channel_code"]) == "SHOPIFYV3" and item["status"] == "blocked" for item in channel_priority):
            readiness_checklist.append({
                "item": "渠道类型",
                "status": "blocked",
                "evidence": "ShopifyV3 不被发布服务支持",
            })
        if any(_normalize_channel(item["channel_code"]) == "SHEIN" and item["status"] == "blocked" for item in channel_priority):
            readiness_checklist.append({
                "item": "渠道属性",
                "status": "blocked",
                "evidence": "SHEIN 缺少商品属性/SKC/销售属性",
            })

        launch_steps = []
        if any(_normalize_channel(item["channel_code"]) == "SHOPIFYV3" and item["status"] == "blocked" for item in channel_priority):
            launch_steps.append({
                "step": len(launch_steps) + 1,
                "title": "检查 ShopifyV3 发布服务支持",
                "actions": ["确认 ShopifyV3 渠道配置与发布服务支持关系"],
                "owner": "渠道运营",
                "priority": "P0",
            })
        if any(_normalize_channel(item["channel_code"]) == "SHEIN" and item["status"] == "blocked" for item in channel_priority):
            launch_steps.append({
                "step": len(launch_steps) + 1,
                "title": "补齐 SHEIN 商品属性",
                "actions": ["补齐 SKC", "补齐销售属性", "补齐商品属性"],
                "owner": "商品运营",
                "priority": "P1",
            })
        if blocked_count:
            launch_steps.append({
                "step": len(launch_steps) + 1,
                "title": "重新执行发布前置诊断",
                "actions": ["重新运行 product-query 和 product-diagnosis"],
                "owner": "Product Agent",
                "priority": "P1",
            })

        return {
            "success": True,
            "summary": (
                f"{identifier} 当前不建议直接发布，{blocked_count} 个渠道存在阻塞项。"
                if blocked_count
                else f"{identifier} 当前目标渠道未发现阻塞项。"
            ),
            "reason": "基于 product-query 的渠道事实和 product-diagnosis 的阻塞项生成发布规划。",
            "evidences": [
                {"source": "product_query", "description": "渠道汇总", "data": channel_summary},
                {"source": "product_diagnosis", "description": "诊断阻塞项", "data": diagnosis_issues},
            ],
            "confidence": "medium",
            "data_completeness": "partial",
            "severity": "major" if blocked_count else None,
            "recommendations": [
                {
                    "action": "complete_listing_readiness",
                    "precondition": "先修复 blocked 渠道的必需数据或 channel type",
                    "risk": "未修复前直接发布会重复失败",
                    "priority": "high" if blocked_count else "low",
                    "expected_effect": "修复后提升渠道发布成功率",
                }
            ],
            "metrics": {
                "target_channel_count": len(target_channels),
                "blocked_channel_count": blocked_count,
                "ready_channel_count": ready_count,
                "launch_step_count": len(launch_steps),
            },
            "details": {
                "channel_priority": channel_priority,
                "readiness_checklist": readiness_checklist,
                "content_plan": {},
                "image_plan": {},
                "launch_steps": launch_steps,
                "risks": [risk for item in channel_priority for risk in item.get("risks", [])],
                "execution_form": execution_form,
                "execution_allowed": execution_allowed,
            },
            "charts": [],
            "visual_blocks": [],
            "links": [],
            "errors": [],
        }
