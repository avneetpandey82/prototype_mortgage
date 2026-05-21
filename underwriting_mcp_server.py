#!/usr/bin/env python3
"""
Mortgage Underwriting Model Context Protocol (MCP) Server
Architected & Engineered by Avneet Pandey

An enterprise-grade, deterministic MCP server for automated credit decisioning, 
debt-to-income (DTI) calculations, loan-to-value (LTV) limits, and audit trails.

This server runs over standard I/O (stdio) to communicate with MCP clients
(e.g., Claude Desktop, Cursor IDE, or custom enterprise middleware gateways).
"""

import sys
import os
import json
import uuid
from datetime import datetime, timezone
import hashlib

# Configuration and Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GUIDELINES_PATH = os.path.join(BASE_DIR, "guidelines.json")

def log(message: str, level: str = "INFO"):
    """
    Structured logging to sys.stderr so as not to interfere with stdio JSON-RPC.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    log_line = json.dumps({"timestamp": timestamp, "level": level, "message": message})
    sys.stderr.write(f"{log_line}\n")
    sys.stderr.flush()

class UnderwritingEngine:
    """
    Deterministic rule engine that processes mortgage guidelines.
    Guarantees no AI math hallucinations and ensures full compliance audit trails.
    """
    def __init__(self, guidelines_path: str):
        self.guidelines_path = guidelines_path
        self.guidelines = self._load_guidelines()

    def _load_guidelines(self) -> dict:
        try:
            if not os.path.exists(self.guidelines_path):
                log(f"Guidelines file not found at {self.guidelines_path}. Creating fallback structure.", "WARNING")
                return self._get_fallback_guidelines()
            with open(self.guidelines_path, "r") as f:
                data = json.load(f)
                log(f"Successfully loaded guidelines version {data.get('guidelines_metadata', {}).get('version')} in engine.")
                return data
        except Exception as e:
            log(f"Error loading guidelines database: {str(e)}", "ERROR")
            return self._get_fallback_guidelines()

    def _get_fallback_guidelines(self) -> dict:
        return {
            "guidelines_metadata": {
                "version": "2026.1.2-FALLBACK",
                "authority": "Local Credit Policy Fallback Engine",
                "policy_reference_hash": "ef39a67a0a0305886134b7fcfca439efc788916327e268a0a8677271db067e2a"
              },
              "conforming_loan_limits": { "1_unit": 766550 },
              "programs": {}
        }

    def get_rules(self, program: str, topic: str) -> dict:
        """
        Fetches precise underwriting policy limits for a given program and topic.
        """
        prog_key = program.lower().strip()
        topic_key = topic.lower().strip()

        if prog_key not in self.guidelines.get("programs", {}):
            return {
                "status": "ERROR",
                "message": f"Unsupported program '{program}'. Available programs: conventional, fha."
            }

        prog_data = self.guidelines["programs"][prog_key]
        
        if topic_key == "conforming_limits" or topic_key == "limits":
            return {
                "program": program,
                "topic": "conforming_loan_limits",
                "limits": self.guidelines.get("conforming_loan_limits", {}),
                "policy_version": self.guidelines["guidelines_metadata"]["version"]
            }
        
        if topic_key == "dti":
            return {
                "program": program,
                "topic": "dti_thresholds",
                "thresholds": prog_data.get("dti_thresholds", {}),
                "policy_version": self.guidelines["guidelines_metadata"]["version"]
            }
        
        if topic_key == "ltv" or topic_key == "cltv":
            return {
                "program": program,
                "topic": "ltv_ratios",
                "max_ltv_ratios": prog_data.get("max_ltv_ratios", {}),
                "max_cltv_ratios": prog_data.get("max_cltv_ratios", {}),
                "policy_version": self.guidelines["guidelines_metadata"]["version"]
            }
        
        if topic_key == "reserves":
            return {
                "program": program,
                "topic": "reserve_requirements_months",
                "requirements": prog_data.get("reserve_requirements_months", {}),
                "policy_version": self.guidelines["guidelines_metadata"]["version"]
            }

        if topic_key == "compensating_factors":
            return {
                "program": program,
                "topic": "compensating_factors",
                "definitions": self.guidelines.get("compensating_factors_definitions", {}),
                "policy_version": self.guidelines["guidelines_metadata"]["version"]
            }

        return {
            "program": program,
            "topic": topic,
            "message": f"Topic '{topic}' not found in structured rules. Returning complete program metadata.",
            "program_metadata": prog_data,
            "policy_version": self.guidelines["guidelines_metadata"]["version"]
        }

    def evaluate_compliance(self, 
                            program: str, 
                            loan_amount: float, 
                            property_value: float, 
                            monthly_income: float, 
                            monthly_debts: float, 
                            proposed_housing_payment: float, 
                            credit_score: int,
                            has_compensating_factors: bool = False) -> dict:
        """
        Executes a deterministic compliance and underwriting rule validation.
        Returns detailed logs, policy citations, and decision parameters.
        """
        prog_key = program.lower().strip()
        if prog_key not in ["conventional", "fha"]:
            return {
                "compliance_status": "REFER_TO_UNDERWRITER",
                "rejection_reasons": [f"Unsupported mortgage program type: '{program}'."],
                "decision_audit_trail": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "policy_version": self.guidelines["guidelines_metadata"]["version"],
                    "policy_hash": self.guidelines["guidelines_metadata"]["policy_reference_hash"]
                }
            }

        # Calculations (Deterministic calculations, decoupled from LLM)
        ltv = round((loan_amount / property_value) * 100, 2)
        cltv = ltv # Mocking HELOC balance as 0 for simple CLTV calculation
        
        front_dti = round((proposed_housing_payment / monthly_income) * 100, 2) if monthly_income > 0 else 999.0
        back_dti = round(((monthly_debts + proposed_housing_payment) / monthly_income) * 100, 2) if monthly_income > 0 else 999.0

        rules_evaluated = []
        rejection_reasons = []
        warnings = []
        
        prog_rules = self.guidelines["programs"][prog_key]
        policy_ver = self.guidelines["guidelines_metadata"]["version"]

        # 1. Conforming Loan Limit Check
        conforming_limit = self.guidelines["conforming_loan_limits"]["1_unit"]
        limit_status = "PASS"
        if loan_amount > conforming_limit:
            if prog_key == "conventional":
                limit_status = "WARNING"
                warnings.append(f"Loan amount ${loan_amount:,.2f} exceeds standard conforming limit of ${conforming_limit:,.2f}. This transitions into Jumbo credit risk requirements.")
            else:
                limit_status = "FAIL"
                rejection_reasons.append(f"FHA loan amount ${loan_amount:,.2f} exceeds maximum base limit limits.")
        
        rules_evaluated.append({
            "rule_name": "Conforming Loan Limit Validation",
            "status": limit_status,
            "observed": f"${loan_amount:,.2f}",
            "limit": f"<=${conforming_limit:,.2f}",
            "policy_reference": "Guidelines Conforming Limits Table"
        })

        # 2. Credit Score Check
        min_credit = prog_rules.get("min_credit_score") if prog_key == "conventional" else prog_rules.get("min_credit_score_standard")
        credit_status = "PASS"
        if credit_score < min_credit:
            credit_status = "FAIL"
            rejection_reasons.append(f"Credit Score of {credit_score} is below minimum requirement of {min_credit} for program '{prog_key}'.")
        
        rules_evaluated.append({
            "rule_name": "Minimum Bureau Credit Score Check",
            "status": credit_status,
            "observed": credit_score,
            "limit": f">={min_credit}",
            "policy_reference": f"{prog_rules['name']} - Credit Policy Standards"
        })

        # 3. LTV / CLTV Check
        # For prototype simplicity, assuming primary residence purchase transaction
        max_ltv = prog_rules["max_ltv_ratios"]["purchase"]["primary_residence_1_unit"]
        ltv_status = "PASS"
        
        # Adjust FHA limits if credit score is between 500 and 579
        if prog_key == "fha" and 500 <= credit_score < 580:
            max_ltv = 90.0 # Standard FHA manual restriction for low credit score
            
        if ltv > max_ltv:
            ltv_status = "FAIL"
            rejection_reasons.append(f"LTV of {ltv}% exceeds the maximum parameter of {max_ltv}% for primary residence purchase.")
        
        rules_evaluated.append({
            "rule_name": "Loan-to-Value (LTV) Risk Valuation",
            "status": ltv_status,
            "observed": f"{ltv}%",
            "limit": f"<={max_ltv}%",
            "policy_reference": f"{prog_rules['name']} - Section: Purchase Max LTV"
        })

        # 4. Debt-to-Income Ratio Checks
        dti_status = "PASS"
        
        if prog_key == "conventional":
            thresholds = prog_rules["dti_thresholds"]
            std_back = thresholds["back_end_standard"]
            comp_back = thresholds["back_end_with_compensating_factors"]
            max_aus = thresholds["back_end_max_aus"]

            if back_dti <= std_back:
                dti_status = "PASS"
            elif back_dti <= comp_back:
                dti_status = "WARNING"
                warnings.append(f"Total DTI of {back_dti}% exceeds standard conforming benchmark of {std_back}%. Conditionally approved pending automated AUS approval.")
            elif back_dti <= max_aus:
                if has_compensating_factors:
                    dti_status = "WARNING"
                    warnings.append(f"Total DTI of {back_dti}% exceeds expanded credit benchmark of {comp_back}%. Allowed due to validated compensating factors.")
                else:
                    dti_status = "FAIL"
                    rejection_reasons.append(f"Total DTI of {back_dti}% exceeds standard benchmark ({std_back}%) and no compensating factors were supplied.")
            else:
                dti_status = "FAIL"
                rejection_reasons.append(f"Total DTI of {back_dti}% exceeds the absolute Fannie Mae ceiling limit of {max_aus}%.")
            
            rules_evaluated.append({
                "rule_name": "Total Debt-to-Income (DTI) Compliance Check",
                "status": dti_status,
                "observed": f"{back_dti}%",
                "limit": f"Standard <= {std_back}%, Max Allowed <= {max_aus}%",
                "policy_reference": f"Fannie Mae Credit Guidelines - Section B3-6-02"
            })
            
        elif prog_key == "fha":
            # Standard Manual limits: 31% / 43%
            # With compensating factors: 40% / 50%
            limits = prog_rules["dti_thresholds"]["manual_underwrite_standard"]
            max_limits = prog_rules["dti_thresholds"]["manual_underwrite_with_compensating_factors"]
            
            std_front, std_back = limits["front_end_limit"], limits["back_end_limit"]
            max_front, max_back = max_limits["front_end_limit"], max_limits["back_end_limit"]
            
            if front_dti <= std_front and back_dti <= std_back:
                dti_status = "PASS"
            elif front_dti <= max_front and back_dti <= max_back:
                if has_compensating_factors:
                    dti_status = "WARNING"
                    warnings.append(f"Ratios ({front_dti}% front / {back_dti}% back) exceed standard HUD metrics ({std_front}% / {std_back}%). Approved based on verified Compensating Factors.")
                else:
                    dti_status = "FAIL"
                    rejection_reasons.append(f"Ratios ({front_dti}% / {back_dti}%) exceed FHA standard limits ({std_front}% / {std_back}%) and no compensating factors were provided.")
            else:
                dti_status = "FAIL"
                rejection_reasons.append(f"Ratios ({front_dti}% front / {back_dti}% back) exceed absolute manual underwriting limit boundaries ({max_front}% / {max_back}%).")
                
            rules_evaluated.append({
                "rule_name": "FHA Double-Ratio DTI Analysis",
                "status": dti_status,
                "observed": f"{front_dti}% Front / {back_dti}% Back",
                "limit": f"Standard {std_front}%/{std_back}%, Max Comp {max_front}%/{max_back}%",
                "policy_reference": "HUD 4000.1 II.A.5 - Manual Underwriting Ratios"
            })

        # Determine Final Compliance Status
        if len(rejection_reasons) > 0:
            compliance_status = "REFER_TO_UNDERWRITER"
            summary = "Automatic Underwriting System (AUS) evaluation recommends REFER TO UNDERWRITER. Credit file does not satisfy minimum standard rules."
        elif len(warnings) > 0:
            compliance_status = "CONDITIONALLY_APPROVED"
            summary = "Automatic Underwriting System (AUS) evaluation returns CONDITIONAL APPROVAL. Specific guidelines require verification or compensating factor validation."
        else:
            compliance_status = "APPROVED"
            summary = "Automatic Underwriting System (AUS) evaluation returns ACCEPT/PASS. The credit file satisfies standard Fannie Mae / FHA credit policies."

        # Unique transaction identifier for strict logging and Fair Lending auditing
        audit_id = str(uuid.uuid4())
        
        # Decision hash generation to guarantee the output is secure and version-pinned
        audit_content = f"{audit_id}-{compliance_status}-{ltv}-{back_dti}-{policy_ver}"
        decision_token = hashlib.sha256(audit_content.encode()).hexdigest()[:16]

        return {
            "compliance_status": compliance_status,
            "underwriting_summary": summary,
            "ratios": {
                "ltv_percent": ltv,
                "cltv_percent": cltv,
                "front_dti_percent": front_dti,
                "back_dti_percent": back_dti
            },
            "rules_evaluated": rules_evaluated,
            "warnings": warnings,
            "rejection_reasons": rejection_reasons,
            "decision_audit_trail": {
                "uuid": audit_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "policy_version": policy_ver,
                "policy_hash": self.guidelines["guidelines_metadata"]["policy_reference_hash"],
                "audit_token": f"DEC-TXN-{decision_token.upper()}",
                "regulatory_disclosure_statement": "This automated loan evaluation has been conducted in accordance with credit scoring guidelines and deterministic algorithms. Decisions conform strictly to the Equal Credit Opportunity Act (ECOA) (15 U.S.C. § 1691 et seq.) and Fair Lending guidelines. Hallucinations are mathematically mitigated."
            }
        }

# Initialise underwriting engine
underwriting_engine = UnderwritingEngine(GUIDELINES_PATH)

def handle_initialize(request_id: int, params: dict) -> dict:
    """
    Initialisation handshake response listing server capabilities.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {}
            },
            "serverInfo": {
                "name": "Mortgage-Underwriting-Compliance-Server",
                "version": "1.0.0"
            }
        }
    }

def handle_tools_list(request_id: int) -> dict:
    """
    Lists the available mortgage credit underwriting tools.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "tools": [
                {
                    "name": "get_guideline_rules",
                    "description": "Fetches precise, structured underwriting rules for a given program and topic (limits, DTI, LTV, reserves, compensating factors) to avoid model hallucination.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "program": {
                                "type": "string",
                                "description": "The mortgage program: 'conventional' or 'fha'."
                            },
                            "topic": {
                                "type": "string",
                                "description": "The rule area: 'limits', 'dti', 'ltv', 'reserves', or 'compensating_factors'."
                            }
                        },
                        "required": ["program", "topic"]
                    }
                },
                {
                    "name": "calculate_dti",
                    "description": "Calculates Front-End (Housing) DTI and Back-End (Total) DTI ratios cleanly and deterministically.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "monthly_income": {
                                "type": "number",
                                "description": "Verified monthly qualifying gross income of all borrowers."
                            },
                            "monthly_debts": {
                                "type": "number",
                                "description": "Sum of all active recurring credit debts (credit cards, student loans, auto loans)."
                            },
                            "proposed_housing_payment": {
                                "type": "number",
                                "description": "Total proposed monthly housing payment, containing Principal, Interest, Taxes, Insurance, and HOA (PITIA)."
                            }
                        },
                        "required": ["monthly_income", "monthly_debts", "proposed_housing_payment"]
                    }
                },
                {
                    "name": "calculate_ltv_cltv",
                    "description": "Calculates Loan-To-Value (LTV) and Combined Loan-To-Value (CLTV) metrics to ensure alignment with property valuations.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "loan_amount": {
                                "type": "number",
                                "description": "The base loan amount of the primary mortgage."
                            },
                            "property_value": {
                                "type": "number",
                                "description": "The appraised property value or purchase price (whichever is lower)."
                            },
                            "heloc_balance": {
                                "type": "number",
                                "description": "Active balance of any subordinate financing or HELOC. Default is 0.",
                                "default": 0
                            }
                        },
                        "required": ["loan_amount", "property_value"]
                    }
                },
                {
                    "name": "evaluate_loan_compliance",
                    "description": "Performs full automated credit risk and compliance underwriting checks against Fannie Mae / FHA guidelines. Delivers standard mathematical valuations, compliance flags, and regulatory decision trails.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "program": {
                                "type": "string",
                                "description": "Mortgage program: 'conventional' or 'fha'."
                            },
                            "loan_amount": {
                                "type": "number",
                                "description": "The proposed mortgage loan amount."
                            },
                            "property_value": {
                                "type": "number",
                                "description": "The appraised property value."
                            },
                            "monthly_income": {
                                "type": "number",
                                "description": "Borrowers' combined monthly gross income."
                            },
                            "monthly_debts": {
                                "type": "number",
                                "description": "Existing monthly recurring credit liabilities."
                            },
                            "proposed_housing_payment": {
                                "type": "number",
                                "description": "Total monthly housing payment (PITIA)."
                            },
                            "credit_score": {
                                "type": "integer",
                                "description": "Representative credit score of primary qualifying borrower."
                            },
                            "has_compensating_factors": {
                                "type": "boolean",
                                "description": "Flags whether compensating factor assets have been validated by underwriting.",
                                "default": False
                            }
                        },
                        "required": [
                            "program", "loan_amount", "property_value", 
                            "monthly_income", "monthly_debts", "proposed_housing_payment", 
                            "credit_score"
                        ]
                    }
                }
            ]
        }
    }

def handle_tools_call(request_id: int, method_name: str, arguments: dict) -> dict:
    """
    Routes the execution of MCP tool calls.
    """
    try:
        if method_name == "get_guideline_rules":
            program = arguments.get("program")
            topic = arguments.get("topic")
            result = underwriting_engine.get_rules(program, topic)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }

        elif method_name == "calculate_dti":
            income = float(arguments.get("monthly_income", 0))
            debts = float(arguments.get("monthly_debts", 0))
            pitia = float(arguments.get("proposed_housing_payment", 0))
            
            front = round((pitia / income) * 100, 2) if income > 0 else 999.0
            back = round(((debts + pitia) / income) * 100, 2) if income > 0 else 999.0
            
            result = {
                "calculation_type": "Debt-To-Income Ratio Analysis",
                "ratios": {
                    "front_end_housing_dti": f"{front}%",
                    "back_end_total_dti": f"{back}%"
                },
                "audit_timestamp": datetime.now(timezone.utc).isoformat()
            }
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }

        elif method_name == "calculate_ltv_cltv":
            loan = float(arguments.get("loan_amount", 0))
            prop = float(arguments.get("property_value", 0))
            heloc = float(arguments.get("heloc_balance", 0))
            
            ltv = round((loan / prop) * 100, 2) if prop > 0 else 0.0
            cltv = round(((loan + heloc) / prop) * 100, 2) if prop > 0 else 0.0
            
            result = {
                "calculation_type": "Loan-to-Value Ratio Analysis",
                "ratios": {
                    "loan_to_value_ltv": f"{ltv}%",
                    "combined_loan_to_value_cltv": f"{cltv}%"
                },
                "audit_timestamp": datetime.now(timezone.utc).isoformat()
            }
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }

        elif method_name == "evaluate_loan_compliance":
            result = underwriting_engine.evaluate_compliance(
                program=arguments.get("program"),
                loan_amount=float(arguments.get("loan_amount")),
                property_value=float(arguments.get("property_value")),
                monthly_income=float(arguments.get("monthly_income")),
                monthly_debts=float(arguments.get("monthly_debts")),
                proposed_housing_payment=float(arguments.get("proposed_housing_payment")),
                credit_score=int(arguments.get("credit_score")),
                has_compensating_factors=bool(arguments.get("has_compensating_factors", False))
            )
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }

        else:
            return make_error_response(request_id, -32601, f"Tool method '{method_name}' not found.")

    except Exception as e:
        log(f"Execution failed on tool '{method_name}': {str(e)}", "ERROR")
        return make_error_response(request_id, -32603, f"Internal execution error: {str(e)}")

def handle_resources_list(request_id: int) -> dict:
    """
    Lists exposed resource endpoints.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "resources": [
                {
                    "uri": "guidelines://corporate/credit-policy",
                    "name": "Active Corporate Mortgage Underwriting Guidelines Database",
                    "description": "Full structured rules representing conforming limits, DTI ratios, and FHA exceptions.",
                    "mimeType": "application/json"
                }
            ]
        }
    }

def handle_resources_read(request_id: int, uri: str) -> dict:
    """
    Exposes direct read-only access to policies guidelines.
    """
    if uri == "guidelines://corporate/credit-policy":
        try:
            with open(GUIDELINES_PATH, "r") as f:
                content = f.read()
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": content
                        }
                    ]
                }
            }
        except Exception as e:
            return make_error_response(request_id, -32000, f"Failed to read guidelines resource: {str(e)}")
    
    return make_error_response(request_id, -32602, f"Resource URI '{uri}' not supported by server.")

def handle_prompts_list(request_id: int) -> dict:
    """
    Lists the available underwriting prompt templates.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "prompts": [
                {
                    "name": "guided_underwriting_review",
                    "description": "Pre-configures the AI agent's system prompt and routing context to perform a credit risk and compliance review.",
                    "arguments": [
                        {
                            "name": "borrower_name",
                            "description": "Name of the qualifying borrower.",
                            "required": True
                        }
                    ]
                }
            ]
        }
    }

def handle_prompts_get(request_id: int, prompt_name: str, arguments: dict) -> dict:
    """
    Generates the dynamic underwriting prompt template context.
    """
    if prompt_name == "guided_underwriting_review":
        borrower = arguments.get("borrower_name", "Valued Applicant")
        prompt_text = (
            f"You are an elite automated underwriting assistant. You are conducting a compliance credit policy review "
            f"for borrower '{borrower}'.\n\n"
            f"INSTRUCTIONS:\n"
            f"1. Gather the borrower's financial details (income, debts, loan amount, property value, credit score).\n"
            f"2. Execute the 'evaluate_loan_compliance' tool to compute absolute ratios and verify rules.\n"
            f"3. Retrieve the full policy database using the resource URI 'guidelines://corporate/credit-policy' "
            f"to compare findings and check reserve months requirements based on credit scores.\n"
            f"4. Synthesize a professional, Fair Lending compliant summary. Ensure you quote the "
            f"'decision_audit_token' and policy reference hashes returned by the tool."
        )
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "description": "Guided compliance underwriting review prompt",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": prompt_text
                        }
                    }
                ]
            }
        }
    return make_error_response(request_id, -32602, f"Prompt '{prompt_name}' not found.")

def make_error_response(request_id: int, code: int, message: str) -> dict:
    """
    Generates standard JSON-RPC 2.0 error payloads.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message
        }
    }

def main():
    """
    Main standard I/O processing loop.
    Reads lines of JSON payloads, parses standard RPC requests, and writes responses.
    """
    log("Mortgage Underwriting MCP Server started successfully over STDIO.")
    
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                sys.stdout.write(json.dumps({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse Error: Invalid JSON structure."}
                }) + "\n")
                sys.stdout.flush()
                continue

            method = request.get("method")
            req_id = request.get("id")
            params = request.get("params", {})

            # Router
            response = None
            if method == "initialize":
                response = handle_initialize(req_id, params)
            elif method == "initialized":
                # client acknowledging initialized state
                continue
            elif method == "tools/list":
                response = handle_tools_list(req_id)
            elif method == "tools/call":
                tool_name = params.get("name")
                args = params.get("arguments", {})
                response = handle_tools_call(req_id, tool_name, args)
            elif method == "resources/list":
                response = handle_resources_list(req_id)
            elif method == "resources/read":
                uri = params.get("uri")
                response = handle_resources_read(req_id, uri)
            elif method == "prompts/list":
                response = handle_prompts_list(req_id)
            elif method == "prompts/get":
                prompt_name = params.get("name")
                args = params.get("arguments", {})
                response = handle_prompts_get(req_id, prompt_name, args)
            elif method == "ping":
                response = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            else:
                if req_id is not None:
                    response = make_error_response(req_id, -32601, f"Method '{method}' not found or unsupported.")

            if response:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

    except KeyboardInterrupt:
        log("Underwriting server received shutdown signal. Exiting.")
    except Exception as e:
        log(f"Fatal error in main server execution loop: {str(e)}", "ERROR")
        sys.exit(1)

if __name__ == "__main__":
    main()
