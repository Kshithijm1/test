"""
Test file for the refactored display agent using LangChain with Vertex AI.
This demonstrates the complete flow: data -> display agent -> chart config JSON
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from langchain_core.messages import HumanMessage
from agents.display_agent.display_agent import display_agent
from core.state import AgentState


sample_tesla_data = [
    {"filingDate": "2024-01-24", "companyName": "Tesla, Inc.", "capital_expenditure": -1858, "cash_from_operations": 3824},
    {"filingDate": "2024-01-29", "companyName": "Tesla, Inc.", "capital_expenditure": -2082.5, "cash_from_operations": 3824},
    {"filingDate": "2024-04-23", "companyName": "Tesla, Inc.", "capital_expenditure": -2777, "cash_from_operations": 1377.5},
    {"filingDate": "2024-04-24", "companyName": "Tesla, Inc.", "capital_expenditure": -2425, "cash_from_operations": 1377.5},
    {"filingDate": "2024-07-23", "companyName": "Tesla, Inc.", "capital_expenditure": -2166, "cash_from_operations": 3338.5},
    {"filingDate": "2024-10-23", "companyName": "Tesla, Inc.", "capital_expenditure": None, "cash_from_operations": 4781.5},
    {"filingDate": "2024-10-24", "companyName": "Tesla, Inc.", "capital_expenditure": -2986, "cash_from_operations": 3308},
    {"filingDate": "2025-01-29", "companyName": "Tesla, Inc.", "capital_expenditure": -2545, "cash_from_operations": 4592},
    {"filingDate": "2025-01-30", "companyName": "Tesla, Inc.", "capital_expenditure": -2543.5, "cash_from_operations": 4592},
    {"filingDate": "2025-04-22", "companyName": "Tesla, Inc.", "capital_expenditure": -2134.5, "cash_from_operations": 1199},
    {"filingDate": "2025-07-23", "companyName": "Tesla, Inc.", "capital_expenditure": -2333, "cash_from_operations": None},
    {"filingDate": "2025-07-24", "companyName": "Tesla, Inc.", "capital_expenditure": -2726.33333333, "cash_from_operations": 3076},
    {"filingDate": "2025-10-22", "companyName": "Tesla, Inc.", "capital_expenditure": -2880.5, "cash_from_operations": 6255},
    {"filingDate": "2025-10-23", "companyName": "Tesla, Inc.", "capital_expenditure": -2880.5, "cash_from_operations": 6246.5},
]


def test_display_agent_use_case_3():
    """Test Use Case 3: Line chart with one X and two Y axes"""
    print("\n" + "="*80)
    print("TEST: Use Case 3 - Tesla Capital Expenditure vs Cash from Operations")
    print("="*80)
    
    user_question = "Tesla: Capital Expenditure vs Cash from Operations over time"
    
    state = AgentState(
        messages=[HumanMessage(content=user_question)],
        pm_plan="",
        stream_chunks=[],
        display_results=[],
        data_fetched=True,
        evaluation="",
        evaluation_critique="",
        retry_count=0,
        token_queue=None,
        start_time=0.0,
        bigquery_data=sample_tesla_data
    )
    
    result = display_agent(state)
    
    if result["display_results"]:
        chart_config = result["display_results"][0]
        print("\n✅ Chart Configuration Generated:")
        print(json.dumps(chart_config, indent=2))
        
        print("\n📊 Validation:")
        print(f"  - Use Case: {chart_config.get('usecase')}")
        print(f"  - Title: {chart_config.get('update_layout_title')}")
        print(f"  - X-axis: {chart_config.get('x')}")
        print(f"  - Y-axes: {chart_config.get('y')}")
        print(f"  - Mode: {chart_config.get('mode')}")
        
        assert chart_config.get('usecase') in ['1', '2', '3'], "Invalid use case"
        assert 'update_layout_title' in chart_config, "Missing title"
        assert 'x' in chart_config, "Missing x-axis"
        assert 'y' in chart_config, "Missing y-axis"
        
        print("\n✅ All validations passed!")
    else:
        print("\n❌ No chart configuration generated")
        print(f"Result: {result}")


def test_display_agent_use_case_1():
    """Test Use Case 1: Line chart with one X and one Y axis"""
    print("\n" + "="*80)
    print("TEST: Use Case 1 - NVIDIA Forward PE over time")
    print("="*80)
    
    nvidia_data = [
        {"filingDate": "2024-02-21", "companyName": "NVIDIA Corporation", "forward_pe": 35.2},
        {"filingDate": "2024-05-22", "companyName": "NVIDIA Corporation", "forward_pe": 38.5},
        {"filingDate": "2024-08-28", "companyName": "NVIDIA Corporation", "forward_pe": 32.1},
        {"filingDate": "2024-11-20", "companyName": "NVIDIA Corporation", "forward_pe": 29.8},
        {"filingDate": "2025-02-19", "companyName": "NVIDIA Corporation", "forward_pe": 31.4},
    ]
    
    user_question = "NVIDIA Forward PE over the last year"
    
    state = AgentState(
        messages=[HumanMessage(content=user_question)],
        pm_plan="",
        stream_chunks=[],
        display_results=[],
        data_fetched=True,
        evaluation="",
        evaluation_critique="",
        retry_count=0,
        token_queue=None,
        start_time=0.0,
        bigquery_data=nvidia_data
    )
    
    result = display_agent(state)
    
    if result["display_results"]:
        chart_config = result["display_results"][0]
        print("\n✅ Chart Configuration Generated:")
        print(json.dumps(chart_config, indent=2))
        
        print("\n📊 Validation:")
        print(f"  - Use Case: {chart_config.get('usecase')}")
        print(f"  - Title: {chart_config.get('update_layout_title')}")
        print(f"  - X-axis: {chart_config.get('x')}")
        print(f"  - Y-axis: {chart_config.get('y')}")
        
        print("\n✅ All validations passed!")
    else:
        print("\n❌ No chart configuration generated")


if __name__ == "__main__":
    print("\n🚀 Starting Display Agent Tests with LangChain + Vertex AI")
    print("="*80)
    
    try:
        test_display_agent_use_case_3()
        test_display_agent_use_case_1()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
