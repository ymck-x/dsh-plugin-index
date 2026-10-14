/**
 * dsh-plugin-index —— Host 半侧（空壳）。
 *
 * 清单数据已内联进客户端半侧（lib/client.js，由 build-client.py 生成），
 * 所以这里不注册路由、不注入任何服务、不发网络请求。
 *
 * 这个文件唯一的作用是让 Loader 有一个 entry：
 * 客户端半侧只挂在「name 恰为裸包名」的那一行上，没有 host 入口它不会被加载。
 */
export const name = 'dsh-plugin-index'
export const inject = []

export function apply() {
  /* 数据在 client 半，Host 侧无事可做 */
}
