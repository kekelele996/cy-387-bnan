<template>
  <main class="login-page">
    <el-card class="login-card">
      <template #header>
        <div class="login-header">
          <h1>RentFind 物业报修</h1>
          <p>住户报修受理闭环系统</p>
        </div>
      </template>

      <el-tabs v-model="tab">
        <el-tab-pane label="登录" name="login">
          <el-form label-position="top" @submit.prevent>
            <el-form-item label="用户名">
              <el-input v-model="loginForm.username" placeholder="zhangsan / shui" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="loginForm.password" type="password" show-password placeholder="demo1234" />
            </el-form-item>
            <el-button type="primary" class="full" :loading="loading" @click="handleLogin">登录</el-button>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册" name="register">
          <el-form label-position="top" @submit.prevent>
            <el-form-item label="用户名">
              <el-input v-model="registerForm.username" />
            </el-form-item>
            <el-form-item label="密码">
              <el-input v-model="registerForm.password" type="password" show-password />
            </el-form-item>
            <el-form-item label="角色">
              <el-radio-group v-model="registerForm.role">
                <el-radio-button label="租客" />
                <el-radio-button label="物业人员" />
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="registerForm.role === '物业人员'" label="故障处理资质（可多选）">
              <el-checkbox-group v-model="registerForm.qualified_faults">
                <el-checkbox v-for="fault in FAULT_TYPES" :key="fault" :label="fault" />
              </el-checkbox-group>
            </el-form-item>
            <el-button type="success" class="full" :loading="loading" @click="handleRegister">注册</el-button>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <el-alert
        v-if="error"
        :title="error"
        type="error"
        show-icon
        :closable="false"
        class="login-tip"
      />
      <p class="demo-hint">演示账号：住户 zhangsan、物业 shui/suo/guan/jia，密码均为 demo1234</p>
    </el-card>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { login, register } from '../api/repair';
import { useAuth } from '../stores/auth';
import { FAULT_TYPES } from '../constants/repair';

const router = useRouter();
const { setUser } = useAuth();
const tab = ref('login');
const loading = ref(false);
const error = ref('');

const loginForm = reactive({ username: '', password: '' });
const registerForm = reactive<{
  username: string;
  password: string;
  role: '租客' | '物业人员';
  qualified_faults: string[];
}>({ username: '', password: '', role: '租客', qualified_faults: [] });

async function handleLogin() {
  error.value = '';
  loading.value = true;
  try {
    const result = await login(loginForm.username.trim(), loginForm.password);
    setUser(result.user);
    ElMessage.success(`欢迎，${result.user.username}（${result.user.role}）`);
    router.replace({ name: result.user.role === '物业人员' ? 'staff' : 'resident' });
  } catch (err) {
    error.value = err instanceof Error ? err.message : '登录失败';
  } finally {
    loading.value = false;
  }
}

async function handleRegister() {
  error.value = '';
  if (!registerForm.username || !registerForm.password) {
    error.value = '请填写用户名和密码';
    return;
  }
  loading.value = true;
  try {
    await register({
      username: registerForm.username.trim(),
      password: registerForm.password,
      role: registerForm.role,
      qualified_faults: registerForm.role === '物业人员' ? registerForm.qualified_faults : [],
    });
    ElMessage.success('注册成功，请使用新账号登录');
    tab.value = 'login';
    loginForm.username = registerForm.username;
    loginForm.password = registerForm.password;
  } catch (err) {
    error.value = err instanceof Error ? err.message : '注册失败';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #e8f1ff 0%, #f6f8fb 100%);
  padding: 24px;
}
.login-card { width: 440px; max-width: 100%; }
.login-header h1 { margin: 0; font-size: 22px; }
.login-header p { margin: 6px 0 0; color: #6b778c; font-size: 13px; }
.full { width: 100%; }
.login-tip { margin-top: 14px; }
.demo-hint { margin-top: 12px; font-size: 12px; color: #8a93a5; text-align: center; }
</style>
