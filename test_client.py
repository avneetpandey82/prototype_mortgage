#!/usr/bin/env python3
"""
Mortgage Underwriting MCP Server Integration Test Client
Simulates an MCP client by spawning the underwriting server as a subprocess,
sending JSON-RPC payloads via standard input, and verifying the responses.
"""

import subprocess
import json
import sys
import os
import time

def print_banner(title):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)

def send_request(proc, request):
    """
    Sends a single JSON-RPC request to the subprocess stdin and returns parsed response.
    """
    payload = json.dumps(request) + "\n"
    proc.stdin.write(payload)
    proc.stdin.flush()
    
    # Read response line
    line = proc.stdout.readline()
    if not line:
        return None
    return json.loads(line.strip())

def main():
    print_banner("STARTING MORTGAGE UNDERWRITING MCP SERVER INTEGRATION TESTS")
    
    server_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "underwriting_mcp_server.py")
    
    # Spawn server process
    # Use python executable specifically to handle cross-platform environments
    proc = subprocess.Popen(
        [sys.executable, server_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Wait a small instant for startup logs
    time.sleep(0.5)
    
    tests_failed = 0
    
    try:
        # TEST 1: Protocol Handshake (initialize)
        print("\n[TEST 1] Testing MCP Server Handshake (initialize)...")
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "Integration-Test-Client", "version": "1.0.0"}
            }
        }
        res = send_request(proc, init_req)
        if res and "result" in res and res["result"]["serverInfo"]["name"] == "Mortgage-Underwriting-Compliance-Server":
            print("  [PASS] MCP handshake succeeded. Capabilities exchanged.")
        else:
            print("  [FAIL] Handshake failed.")
            tests_failed += 1
            
        # TEST 2: List Underwriting Tools
        print("\n[TEST 2] Testing Tools Directory Lookup (tools/list)...")
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }
        res = send_request(proc, list_req)
        if res and "result" in res and "tools" in res["result"]:
            tool_names = [t["name"] for t in res["result"]["tools"]]
            print(f"  [PASS] Received {len(tool_names)} tools: {', '.join(tool_names)}")
            assert "calculate_dti" in tool_names
            assert "evaluate_loan_compliance" in tool_names
        else:
            print("  [FAIL] Tool listing failed.")
            tests_failed += 1

        # TEST 3: Deterministic DTI Calculation
        print("\n[TEST 3] Testing Front-End & Back-End DTI Tool Execution (calculate_dti)...")
        dti_req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "calculate_dti",
                "arguments": {
                    "monthly_income": 10000.00,
                    "monthly_debts": 1000.00,
                    "proposed_housing_payment": 2500.00
                }
            }
        }
        res = send_request(proc, dti_req)
        if res and "result" in res and "content" in res["result"]:
            content = json.loads(res["result"]["content"][0]["text"])
            front_dti = content["ratios"]["front_end_housing_dti"]
            back_dti = content["ratios"]["back_end_total_dti"]
            print(f"  [PASS] Calculated DTI: Front-End = {front_dti}, Back-End = {back_dti}")
            if front_dti == "25.0%" and back_dti == "35.0%":
                print("    [OK] Math check passed perfectly.")
            else:
                print("    [FAIL] Math calculation discrepancy.")
                tests_failed += 1
        else:
            print("  [FAIL] DTI calculation failed.")
            tests_failed += 1

        # TEST 4: Deterministic LTV Check
        print("\n[TEST 4] Testing Loan-To-Value Calculation Tool (calculate_ltv_cltv)...")
        ltv_req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "calculate_ltv_cltv",
                "arguments": {
                    "loan_amount": 400000.00,
                    "property_value": 500000.00
                }
            }
        }
        res = send_request(proc, ltv_req)
        if res and "result" in res and "content" in res["result"]:
            content = json.loads(res["result"]["content"][0]["text"])
            ltv = content["ratios"]["loan_to_value_ltv"]
            cltv = content["ratios"]["combined_loan_to_value_cltv"]
            print(f"  [PASS] Calculated ratios: LTV = {ltv}, CLTV = {cltv}")
            if ltv == "80.0%" and cltv == "80.0%":
                print("    [OK] Math check passed perfectly.")
            else:
                print("    [FAIL] Math calculation discrepancy.")
                tests_failed += 1
        else:
            print("  [FAIL] LTV calculation failed.")
            tests_failed += 1

        # TEST 5: Complete Compliance Checklist - Clean Approval Case
        print("\n[TEST 5] Testing Fully Compliant Underwriting Case (evaluate_loan_compliance)...")
        comp_req_ok = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "evaluate_loan_compliance",
                "arguments": {
                    "program": "conventional",
                    "loan_amount": 350000.00,
                    "property_value": 450000.00,
                    "monthly_income": 12000.00,
                    "monthly_debts": 800.00,
                    "proposed_housing_payment": 2200.00,
                    "credit_score": 760
                }
            }
        }
        res = send_request(proc, comp_req_ok)
        if res and "result" in res and "content" in res["result"]:
            decision = json.loads(res["result"]["content"][0]["text"])
            status = decision["compliance_status"]
            audit_trail = decision["decision_audit_trail"]
            print(f"  [PASS] Decision = {status}")
            print(f"  [PASS] Summary: {decision['underwriting_summary']}")
            print(f"  [PASS] Audit ID: {audit_trail['uuid']}")
            print(f"  [PASS] Decision Audit Token: {audit_trail['audit_token']}")
            if status == "APPROVED":
                print("    [OK] Compliance rule passing verified.")
            else:
                print(f"    [FAIL] Expected APPROVED, received {status}")
                tests_failed += 1
        else:
            print("  [FAIL] Underwriting check failed.")
            tests_failed += 1

        # TEST 6: Complete Compliance Checklist - High DTI Rejection & Compensating Factors Case
        print("\n[TEST 6] Testing Edge-Case Credit Checking (evaluate_loan_compliance)...")
        # Income $6,000, proposed payment $2,500, debt $400. Total DTI = 2900 / 6000 = 48.33% DTI
        # Standard conventional threshold is 36%. Max with compensating factors is 50%.
        
        print("  Evaluating Conventional loan with 48.33% DTI and NO compensating factors...")
        comp_req_fail = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "evaluate_loan_compliance",
                "arguments": {
                    "program": "conventional",
                    "loan_amount": 300000.00,
                    "property_value": 400000.00,
                    "monthly_income": 6000.00,
                    "monthly_debts": 400.00,
                    "proposed_housing_payment": 2500.00,
                    "credit_score": 700,
                    "has_compensating_factors": False
                }
            }
        }
        res_fail = send_request(proc, comp_req_fail)
        decision_fail = json.loads(res_fail["result"]["content"][0]["text"])
        
        print("  Evaluating Conventional loan with 48.33% DTI and WITH compensating factors...")
        comp_req_warn = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "evaluate_loan_compliance",
                "arguments": {
                    "program": "conventional",
                    "loan_amount": 300000.00,
                    "property_value": 400000.00,
                    "monthly_income": 6000.00,
                    "monthly_debts": 400.00,
                    "proposed_housing_payment": 2500.00,
                    "credit_score": 700,
                    "has_compensating_factors": True
                }
            }
        }
        res_warn = send_request(proc, comp_req_warn)
        decision_warn = json.loads(res_warn["result"]["content"][0]["text"])
        
        print(f"    - Status without compensating factors: {decision_fail['compliance_status']}")
        print(f"      Rejection Reason: {decision_fail['rejection_reasons'][0]}")
        print(f"    - Status with compensating factors: {decision_warn['compliance_status']}")
        print(f"      Warning Issued: {decision_warn['warnings'][0]}")
        
        if decision_fail['compliance_status'] == "REFER_TO_UNDERWRITER" and decision_warn['compliance_status'] == "CONDITIONALLY_APPROVED":
            print("  [PASS] Edge-case compensating factor logic validated perfectly.")
        else:
            print("  [FAIL] Compensating factors rule evaluation logic error.")
            tests_failed += 1

        # TEST 7: Guidelines Resource Read-Only Access
        print("\n[TEST 7] Testing Policy Guidelines File Resource Retrieval (resources/read)...")
        res_read_req = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "resources/read",
            "params": {
                "uri": "guidelines://corporate/credit-policy"
            }
        }
        res = send_request(proc, res_read_req)
        if res and "result" in res and "contents" in res["result"]:
            resource_text = res["result"]["contents"][0]["text"]
            guidelines_db = json.loads(resource_text)
            ver = guidelines_db["guidelines_metadata"]["version"]
            print(f"  [PASS] Retrieved policy file resource. Active version = {ver}")
            print(f"  [PASS] Authority: {guidelines_db['guidelines_metadata']['authority']}")
        else:
            print("  [FAIL] Guidelines resource reading failed.")
            tests_failed += 1

        # TEST 8: Prompts Listing and Fetching
        print("\n[TEST 8] Testing MCP Prompts Registration (prompts/list and prompts/get)...")
        prompts_list_req = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "prompts/list"
        }
        res = send_request(proc, prompts_list_req)
        if res and "result" in res and "prompts" in res["result"]:
            prompt_names = [p["name"] for p in res["result"]["prompts"]]
            print(f"  [PASS] Retrieved prompts list: {', '.join(prompt_names)}")
            assert "guided_underwriting_review" in prompt_names
            
            # Fetch the prompt template
            prompts_get_req = {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "prompts/get",
                "params": {
                    "name": "guided_underwriting_review",
                    "arguments": {
                        "borrower_name": "Jane Doe"
                    }
                }
            }
            res_get = send_request(proc, prompts_get_req)
            if res_get and "result" in res_get and "messages" in res_get["result"]:
                text_content = res_get["result"]["messages"][0]["content"]["text"]
                print("  [PASS] Fetched guided review prompt template successfully.")
                if "Jane Doe" in text_content:
                    print("    [OK] Dynamic argument rendering verified successfully.")
                else:
                    print("    [FAIL] Prompt argument injection failing.")
                    tests_failed += 1
            else:
                print("    [FAIL] Prompt template retrieval failing.")
                tests_failed += 1
        else:
            print("  [FAIL] Prompts listing failed.")
            tests_failed += 1

    finally:
        # Shutdown Server subprocess cleanly
        proc.terminate()
        proc.wait()
        
    print_banner("INTEGRATION TESTS RUN COMPLETED")
    if tests_failed == 0:
        print("  ALL TESTS PASSED SUCCESSFULLY! THE SERVER IS AUDIT-READY.")
        sys.exit(0)
    else:
        print(f"  ERROR: {tests_failed} test(s) failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
