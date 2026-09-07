import { LoginForm } from "../../../features/user/components/LoginForm";

export default function LoginPage() {
  return (
    <div className="loginbg">
      <div className="logincard">
        <div className="lg-logo">
          <span className="dot">枢</span>
          <b>问枢 Pivot</b>
        </div>
        <div className="lg-sub">企业文档智能问答系统 · 登录</div>
        <LoginForm />
        <div className="lg-foot">
          内部系统 · 仅限公司员工使用
          <br />
          忘记密码请联系管理员重置
        </div>
      </div>
    </div>
  );
}
