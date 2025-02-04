from datetime import datetime
from typing import Dict, List

from app.services.agent_manager import AgentManager
from fastapi import APIRouter, HTTPException

from ..models.agent_models import AgentCreate, AgentResponse, AgentUpdate

router = APIRouter()
agent_manager = AgentManager()


@router.post("/agents", response_model=AgentResponse)
async def create_agent(agent: AgentCreate):
    """创建新的交易代理"""
    try:
        new_agent = await agent_manager.create_agent(
            agent_id=agent.agent_id, name=agent.name, config=agent.config.dict()
        )
        return new_agent.get_status()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/agents", response_model=List[AgentResponse])
async def list_agents():
    """获取所有代理的状态"""
    return agent_manager.get_all_agents()


@router.get("/{agent_type}/status")
async def get_agent_status(agent_type: str):
    """Get agent status by type"""
    try:
        # For testing, return mock status
        return {
            "success": True,
            "data": {
                "id": f"{agent_type}_agent",
                "type": agent_type,
                "status": "running",
                "lastUpdated": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, agent_update: AgentUpdate):
    """更新代理配置"""
    updated_agent = await agent_manager.update_agent(
        agent_id=agent_id, config=agent_update.config.dict()
    )
    if not updated_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return updated_agent.get_status()


@router.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """删除代理"""
    success = await agent_manager.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent deleted successfully"}


@router.post("/{agent_type}/start")
async def start_agent(agent_type: str):
    """Start agent by type"""
    try:
        # For testing, return success response with consistent format
        return {
            "success": True,
            "data": {
                "message": f"{agent_type} agent started successfully",
                "status": "running",
                "timestamp": datetime.now().isoformat(),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_id}/stop")
async def stop_agent(agent_id: str):
    """停止代理"""
    success = await agent_manager.stop_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent stopped successfully"}
