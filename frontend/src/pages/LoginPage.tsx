import { SSO_PROVIDER_NAME, buildLoginUrl } from '../auth'

/** Brand landing page: a single "sign in with SSO" link. The password form lives on the auth service only. */
export default function LoginPage() {
  const returnTo = new URLSearchParams(location.search).get('return')
    || `${location.origin}/`
  return (
    <div className="login-root">
      <div className="login-panel">
        <div>
          <div className="login-panel-logo">AI<em>Box</em></div>
          <div className="login-panel-tagline">GenAI 百宝箱</div>
        </div>
        <div className="login-panel-footer">© iX · v{__APP_VERSION__}</div>
      </div>
      <div className="login-form-area">
        <div className="login-card">
          <div className="login-card-title">欢迎使用 AIBox</div>
          <div className="login-card-sub">你的 GenAI 工具箱</div>
          <a className="login-submit" href={buildLoginUrl(returnTo)} style={{ textAlign: 'center', display: 'block', textDecoration: 'none', marginTop: '1.5rem' }}>
            使用 {SSO_PROVIDER_NAME} (SSO) 登录
          </a>
        </div>
      </div>
    </div>
  )
}
