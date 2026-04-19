"""
SPARTA 输入文件模板系统

基于 SPARTA examples 目录中的经过验证的示例构建。
论文显示：模板场景 FPSR=85% vs 自定义场景 FPSR=70%

常用模板来源: sparta/examples/
"""

from typing import Dict, Optional, List
from pathlib import Path
import os

# SPARTA examples 目录路径
SPARTA_EXAMPLES_DIR = Path(os.getenv('SPARTA_DIR', str(Path(__file__).parent.parent / "sparta" / "examples")))


class SPARTATemplate:
    """SPARTA 模板类"""

    def __init__(
        self,
        name: str,
        name_zh: str,
        description: str,
        example_dir: str,
        input_file: str,
        geometry_type: str,
        dimension: int,
        parameters: Dict = None,
        notes: str = ""
    ):
        self.name = name
        self.name_zh = name_zh
        self.description = description
        self.example_dir = example_dir  # examples 下的目录名
        self.input_file = input_file  # 输入文件名（如 in.sphere）
        self.geometry_type = geometry_type  # 几何类型
        self.dimension = dimension  # 2D 或 3D
        self.parameters = parameters or {}
        self.notes = notes

    @property
    def example_path(self) -> Path:
        """返回示例目录的完整路径"""
        return SPARTA_EXAMPLES_DIR / self.example_dir

    @property
    def input_file_path(self) -> Path:
        """返回输入文件的完整路径"""
        return self.example_path / self.input_file

    @property
    def geometry_file(self) -> Optional[str]:
        """返回几何文件名（如果有）"""
        # 从输入文件中提取 read_surf 后的文件名
        if self.input_file_path.exists():
            with open(self.input_file_path, 'r') as f:
                content = f.read()
                import re
                match = re.search(r'read_surf\s+(\S+)', content)
                if match:
                    return match.group(1)
        return None


# 基于 SPARTA examples 的模板定义
TEMPLATES: List[SPARTATemplate] = [
    # ===== 2D 模板 =====
    SPARTATemplate(
        name="circle_2d",
        name_zh="2D圆绕流",
        description="2D超声速/亚声速圆绕流，经典验证用例",
        example_dir="circle",
        input_file="in.circle",
        geometry_type="circle",
        dimension=2,
        parameters={
            "velocity_range": "100-1000",
            "gas": "air",
            "typical_grid": "20x20",
        },
        notes="标准2D测试用例"
    ),

    SPARTATemplate(
        name="plane_2d",
        name_zh="2D平面流动",
        description="2D平面/平板绕流",
        example_dir="circle",
        input_file="in.circle",
        geometry_type="plane",
        dimension=2,
        parameters={
            "velocity_range": "100-1000",
            "gas": "air",
        },
        notes="使用 data.plane1 或 data.plane2"
    ),

    # ===== 3D 模板 =====
    SPARTATemplate(
        name="sphere_3d",
        name_zh="3D球体绕流",
        description="3D高超声速球体绕流，典型再入场景",
        example_dir="sphere",
        input_file="in.sphere",
        geometry_type="sphere",
        dimension=3,
        parameters={
            "velocity_range": "100-10000",
            "gas": "air",
            "typical_grid": "20x20x20",
        },
        notes="适用于高超声速再入仿真"
    ),

    SPARTATemplate(
        name="cylinder_3d",
        name_zh="3D圆柱绕流",
        description="3D圆柱绕流流动",
        example_dir="cylinder",
        input_file="in.cylinder",
        geometry_type="cylinder",
        dimension=3,
        parameters={
            "velocity_range": "100-1000",
            "gas": "air",
        },
        notes="圆柱几何"
    ),

    # ===== 特殊用途模板 =====
    SPARTATemplate(
        name="shock_tube",
        name_zh="激波管",
        description="Sod激波管问题，经典验证用例",
        example_dir="shock_tube",
        input_file="in.shock",
        geometry_type="plane",
        dimension=2,
        parameters={
            "velocity": "0 (stationary)",
            "gas": "N2",
        },
        notes="一维激波管验证"
    ),

    SPARTATemplate(
        name="adapt_grid",
        name_zh="自适应网格",
        description="使用自适应网格的流动仿真",
        example_dir="adapt",
        input_file="in.adapt.rotate",
        geometry_type="circle",
        dimension=2,
        parameters={
            "velocity_range": "100-1000",
            "grid": "adaptive",
        },
        notes="动态网格细化"
    ),

    SPARTATemplate(
        name="surf_collide",
        name_zh="表面碰撞",
        description="粒子与表面碰撞的仿真",
        example_dir="surf_collide",
        input_file="in.circle",
        geometry_type="circle",
        dimension=2,
        parameters={
            "velocity_range": "100-1000",
            "gas": "Ar",
        },
        notes="表面反应和散射研究"
    ),

    SPARTATemplate(
        name="vacuum_chamber",
        name_zh="真空腔室",
        description="低压真空腔室流动",
        example_dir="free",
        input_file="in.free",
        geometry_type="custom",
        dimension=3,
        parameters={
            "pressure": "low (vacuum)",
            "gas": "Ar/N2",
        },
        notes="稀薄气体流动"
    ),

    SPARTATemplate(
        name="emit_particles",
        name_zh="粒子发射",
        description="连续粒子发射仿真",
        example_dir="emit",
        input_file="in.circle",
        geometry_type="circle",
        dimension=2,
        parameters={
            "velocity_range": "100-1000",
            "gas": "Ar",
        },
        notes="喷流和排放研究"
    ),

    SPARTATemplate(
        name="ablation",
        name_zh="烧蚀",
        description="表面烧蚀和化学反应仿真",
        example_dir="ablation",
        input_file="in.ablation.2d",
        geometry_type="custom",
        dimension=2,
        parameters={
            "velocity_range": "5000-10000",
            "gas": "air",
        },
        notes="高超声速飞行器烧蚀"
    ),
]


def get_template(name: str) -> Optional[SPARTATemplate]:
    """根据名称获取模板"""
    for template in TEMPLATES:
        if template.name == name or template.name_zh == name:
            return template
    return None


def get_template_by_geometry(geometry: str, dimension: int = None) -> List[SPARTATemplate]:
    """根据几何类型获取推荐模板"""
    results = []
    geometry_lower = geometry.lower()
    for template in TEMPLATES:
        if template.geometry_type.lower() == geometry_lower:
            if dimension is None or template.dimension == dimension:
                results.append(template)
    return results


def get_template_by_dir(example_dir: str) -> Optional[SPARTATemplate]:
    """根据示例目录名获取模板"""
    for template in TEMPLATES:
        if template.example_dir == example_dir:
            return template
    return None


def list_templates() -> List[Dict]:
    """列出所有可用模板"""
    return [
        {
            "name": t.name,
            "name_zh": t.name_zh,
            "description": t.description,
            "example_dir": t.example_dir,
            "input_file": t.input_file,
            "geometry_type": t.geometry_type,
            "dimension": t.dimension,
            "notes": t.notes,
        }
        for t in TEMPLATES
    ]


def get_all_example_dirs() -> List[str]:
    """获取 SPARTA examples 目录下所有示例目录"""
    if not SPARTA_EXAMPLES_DIR.exists():
        return []
    return [d.name for d in SPARTA_EXAMPLES_DIR.iterdir() if d.is_dir()]


def get_example_input_files(example_dir: str) -> List[str]:
    """获取指定示例目录中的所有输入文件"""
    example_path = SPARTA_EXAMPLES_DIR / example_dir
    if not example_path.exists():
        return []
    return [f.name for f in example_path.iterdir() if f.name.startswith('in.')]


# 几何类型到模板的映射
GEOMETRY_MAPPING = {
    "sphere": "sphere_3d",
    "球体": "sphere_3d",
    "circle": "circle_2d",
    "圆": "circle_2d",
    "cylinder": "cylinder_3d",
    "圆柱": "cylinder_3d",
    "plane": "plane_2d",
    "平面": "plane_2d",
    "step": "circle_2d",
    "阶梯": "circle_2d",
    "shock": "shock_tube",
    "激波管": "shock_tube",
    "vacuum": "vacuum_chamber",
    "真空": "vacuum_chamber",
    "emit": "emit_particles",
    "发射": "emit_particles",
    "ablation": "ablation",
    "烧蚀": "ablation",
}


def get_template_for_geometry(geometry: str, dimension: int = 2) -> Optional[SPARTATemplate]:
    """根据几何类型和维度获取推荐模板"""
    geometry_lower = geometry.lower()
    template_name = GEOMETRY_MAPPING.get(geometry_lower)
    if template_name:
        template = get_template(template_name)
        if template and (dimension is None or template.dimension == dimension):
            return template
    # 如果没有精确匹配，返回第一个几何类型匹配的
    matches = get_template_by_geometry(geometry, dimension)
    return matches[0] if matches else None
