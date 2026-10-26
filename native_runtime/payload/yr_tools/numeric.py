"""One numeric/geometry baseplane; policy is input, never a hidden tolerance."""
import ast,math
from decimal import Decimal,localcontext,ROUND_HALF_EVEN,ROUND_HALF_UP,ROUND_DOWN
from fractions import Fraction
from .binder import need,text,digest,strict_int,ContractError
REVISION='NUMERIC_GEOMETRY_BASEPLANE_R001_PRIVATE'
COMPONENTS={
 'NUMERIC_POLICY_REGISTRY':('revision','numeric_backend_revision','precision_mode','numeric_epsilon','numeric_epsilon_policy_revision','rounding_mode','intermediate_rounding_policy'),
 'COORDINATE_FRAME_REGISTRY':('revision','frames'),
 'ROBUST_PREDICATE_POLICY':('revision','predicate_policy_revision','escalation_precision_rule','ambiguous_topology_disposition'),
 'GEOMETRY_TOLERANCE_POLICY':('revision','quantity_class','geometric_tolerance','domain_tolerance_ref'),
 'ROUNDING_POLICY_REGISTRY':('revision','policies'),
 'CANONICAL_NUMERIC_SERIALIZATION':('revision','serialization_policy_revision','quantity_class','unit_canonicalization','decimal_or_integer_representation','negative_zero_rule','nan_inf_rule')}
UNIT_FACTORS={'1':(Fraction(1),(0,0)),'mm':(Fraction(1,1000),(1,0)),'cm':(Fraction(1,100),(1,0)),'m':(Fraction(1),(1,0)),'km':(Fraction(1000),(1,0)),'inch':(Fraction(127,5000),(1,0)),'ft':(Fraction(381,1250),(1,0)),'yd':(Fraction(1143,1250),(1,0)),'m2':(Fraction(1),(2,0)),'mm2':(Fraction(1,1000000),(2,0)),'m3':(Fraction(1),(3,0)),'mm3':(Fraction(1,1000000000),(3,0)),'rad':(Fraction(1),(0,1)),'deg':(Fraction.from_float(math.pi)/180,(0,1)),'gon':(Fraction.from_float(math.pi)/200,(0,1))}
ROUNDING={'HALF_EVEN':ROUND_HALF_EVEN,'HALF_UP':ROUND_HALF_UP,'DOWN':ROUND_DOWN}
def number(v):
    need(isinstance(v,str) and text(v),'HOLD_TYPED_DECIMAL_REQUIRED')
    need(len(v)<=256,'HOLD_NUMERIC_INPUT_BOUND')
    try:d=Decimal(v)
    except Exception:raise ContractError('HOLD_DECIMAL_TYPE')
    need(d.is_finite(),'HOLD_NAN_INF');need(abs(d.adjusted())<=1000,'HOLD_NUMERIC_EXPONENT_BOUND');return Fraction(d)
def serial(v):
    need(isinstance(v,Fraction),'HOLD_CANONICAL_NUMBER_TYPE')
    return {'representation':'EXACT_RATIONAL','numerator':str(v.numerator),'denominator':str(v.denominator),'negative_zero':False}
def approximate(fn,*values):
    try:r=fn(*(float(v) for v in values))
    except (ValueError,OverflowError,ZeroDivisionError):raise ContractError('HOLD_NUMERIC_DOMAIN')
    need(math.isfinite(r),'HOLD_NUMERIC_NONFINITE');return Fraction.from_float(r)
class Registry:
    def __init__(self,data,pinned_digest):
        need(isinstance(data,dict) and digest(data)==pinned_digest,'HOLD_NUMERIC_REGISTRY_UNBOUND');self.data=data;self.sha256=pinned_digest
        for key,fields in COMPONENTS.items():
            value=data.get(key);need(isinstance(value,dict) and all(k in value for k in fields) and text(value.get('revision')),'HOLD_REGISTRY_'+key)
        np=data['NUMERIC_POLICY_REGISTRY'];need(np['numeric_backend_revision']=='FRACTION_DECIMAL_INPUT_BINARY64_TRANSCENDENTALS_R1','HOLD_BACKEND_UNKNOWN')
        need(np['precision_mode']=='EXACT_RATIONAL_OR_DECLARED_BINARY64' and np['intermediate_rounding_policy']=='PROHIBITED','HOLD_NUMERIC_POLICY_UNKNOWN')
        need(number(np['numeric_epsilon'])>=0,'HOLD_NUMERIC_EPSILON');need(np['rounding_mode'] in ROUNDING,'HOLD_ROUNDING_MODE')
        rp=data['ROBUST_PREDICATE_POLICY'];need(rp['escalation_precision_rule']=='EXACT_RATIONAL' and rp['ambiguous_topology_disposition']=='HOLD','HOLD_PREDICATE_POLICY')
        geom=data['GEOMETRY_TOLERANCE_POLICY'];need(number(geom['geometric_tolerance'])>=0 and isinstance(geom['domain_tolerance_ref'],dict),'HOLD_GEOMETRY_TOLERANCE')
        for frame in data['COORDINATE_FRAME_REGISTRY']['frames'].values():
            need(all(k in frame for k in ('coordinate_frame_id','coordinate_frame_revision','transform_rule_revision','round_trip_tolerance','unit','bearing_convention')),'HOLD_FRAME_DECLARATION')
            need(frame['unit'] in UNIT_FACTORS and UNIT_FACTORS[frame['unit']][1]==(1,0) and number(frame['round_trip_tolerance'])>=0,'HOLD_FRAME_UNIT')
        for policy in data['ROUNDING_POLICY_REGISTRY']['policies'].values():
            need(all(k in policy for k in ('rounding_policy_id','rounding_policy_revision','quantity_class','rounding_stage','rounding_mode','scale_or_digits','authority_source','valid_time')),'HOLD_ROUNDING_DECLARATION')
            need(policy['rounding_stage']=='DISPLAY' and policy['rounding_mode'] in ROUNDING and strict_int(policy['scale_or_digits']) and policy['scale_or_digits']<=30,'HOLD_ROUNDING_POLICY')
        sr=data['CANONICAL_NUMERIC_SERIALIZATION'];need(sr['decimal_or_integer_representation']=='EXACT_RATIONAL' and sr['negative_zero_rule']=='NORMALIZE_ZERO' and sr['nan_inf_rule']=='HOLD','HOLD_SERIALIZATION_POLICY')
    def frame(self,ref):
        need(isinstance(ref,dict),'HOLD_COORDINATE_SYSTEM_UNKNOWN');f=self.data['COORDINATE_FRAME_REGISTRY']['frames'].get(ref.get('id'))
        need(f is not None and ref.get('revision')==f['coordinate_frame_revision'],'HOLD_COORDINATE_FRAME_REVISION');return f
    def display(self,value,ref):
        p=self.data['ROUNDING_POLICY_REGISTRY']['policies'].get(ref.get('id') if isinstance(ref,dict) else None)
        need(p is not None and ref.get('revision')==p['rounding_policy_revision'],'HOLD_ROUNDING_RULE_UNKNOWN')
        with localcontext() as c:
            c.prec=max(80,len(str(abs(value.numerator)))+len(str(value.denominator))+40)
            d=Decimal(value.numerator)/Decimal(value.denominator);q=d.quantize(Decimal(1).scaleb(-p['scale_or_digits']),rounding=ROUNDING[p['rounding_mode']])
            if q==0:q=abs(q)
            return format(q,'f'),p
    def unit(self,value,source,target):
        need(source in UNIT_FACTORS and target in UNIT_FACTORS,'HOLD_UNIT_UNKNOWN');a,ad=UNIT_FACTORS[source];b,bd=UNIT_FACTORS[target]
        need(ad==bd,'HOLD_UNIT_DIMENSION');return value*a/b
    def orient(self,a,b,c):
        value=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]);eps=number(self.data['NUMERIC_POLICY_REGISTRY']['numeric_epsilon'])
        return {'state':'AMBIGUOUS' if abs(value)<=eps else 'POSITIVE' if value>0 else 'NEGATIVE','determinant':serial(value),'disposition':'HOLD' if abs(value)<=eps else 'PASS_EXACT_PREDICATE_ONLY'}
def expression(source,variables):
    """Arithmetic AST only; no eval, attributes, indexing or arbitrary calls."""
    need(text(source) and len(source)<=2000,'HOLD_EXPRESSION_TYPE')
    tree=ast.parse(source,mode='eval');need(sum(1 for _ in ast.walk(tree))<=200,'HOLD_EXPRESSION_BOUND')
    def walk(n):
        if isinstance(n,ast.Name):need(n.id in variables,'HOLD_UNKNOWN_VARIABLE');return variables[n.id]
        if isinstance(n,ast.Constant) and type(n.value) is int:return Fraction(n.value)
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):
            a=walk(n.operand);return a if isinstance(n.op,ast.UAdd) else -a
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):
            a=walk(n.left);b=walk(n.right)
            if isinstance(n.op,ast.Add):return a+b
            if isinstance(n.op,ast.Sub):return a-b
            if isinstance(n.op,ast.Mult):return a*b
            if isinstance(n.op,ast.Div):need(b!=0,'HOLD_DIV_ZERO');return a/b
            need(b.denominator==1 and abs(b)<=64,'HOLD_EXPONENT_BOUND');return a**int(b)
        funcs={'sqrt':math.sqrt,'abs':abs,'exp':math.exp,'log':math.log,'sin':math.sin,'cos':math.cos,'tan':math.tan,'asin':math.asin,'acos':math.acos,'atan':math.atan,'atan2':math.atan2}
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in funcs and not n.keywords:
            args=[walk(a) for a in n.args];need(len(args)==(2 if n.func.id=='atan2' else 1),'HOLD_ARITY')
            return abs(args[0]) if n.func.id=='abs' else approximate(funcs[n.func.id],*args)
        raise ContractError('HOLD_UNSUPPORTED_EXPRESSION')
    return walk(tree.body)

def expression_dimension(source,dimensions):
    tree=ast.parse(source,mode='eval')
    def walk(n):
        if isinstance(n,ast.Name):need(n.id in dimensions,'HOLD_UNKNOWN_VARIABLE');return dimensions[n.id]
        if isinstance(n,ast.Constant) and type(n.value) is int:return (0,0)
        if isinstance(n,ast.UnaryOp):return walk(n.operand)
        if isinstance(n,ast.BinOp):
            a=walk(n.left);b=walk(n.right)
            if isinstance(n.op,(ast.Add,ast.Sub)):need(a==b,'HOLD_UNIT_DIMENSION');return a
            if isinstance(n.op,ast.Mult):return tuple(x+y for x,y in zip(a,b))
            if isinstance(n.op,ast.Div):return tuple(x-y for x,y in zip(a,b))
            if isinstance(n.op,ast.Pow):
                need(isinstance(n.right,ast.Constant) and type(n.right.value) is int and abs(n.right.value)<=64,'HOLD_DIMENSION_EXPONENT');return tuple(x*n.right.value for x in a)
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name):
            dims=[walk(x) for x in n.args];name=n.func.id
            if name=='abs':return dims[0]
            if name=='sqrt':need(all(x%2==0 for x in dims[0]),'HOLD_ROOT_DIMENSION');return tuple(x//2 for x in dims[0])
            if name in {'sin','cos','tan'}:need(dims==[(0,1)],'HOLD_ANGLE_UNIT_UNKNOWN');return (0,0)
            if name in {'asin','acos','atan'}:need(dims==[(0,0)],'HOLD_INVERSE_ANGLE_DIMENSION');return (0,1)
            if name=='atan2':need(len(dims)==2 and dims[0]==dims[1],'HOLD_ATAN2_DIMENSION');return (0,1)
            if name in {'exp','log'}:need(dims==[(0,0)],'HOLD_FUNCTION_DIMENSION');return (0,0)
        raise ContractError('HOLD_UNSUPPORTED_EXPRESSION_DIMENSION')
    return walk(tree.body)
