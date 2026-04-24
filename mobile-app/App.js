import React, { useEffect, useState } from "react";
import { SafeAreaView, StyleSheet, View, ActivityIndicator } from "react-native";
import { StatusBar } from "expo-status-bar";
import AsyncStorage from "@react-native-async-storage/async-storage";
import LoginScreen from "./src/screens/LoginScreen";
import HomeScreen from "./src/screens/HomeScreen";

const SESSION_KEY = "EOSEWS_SESSION";

export default function App() {
  const [booting, setBooting] = useState(true);
  const [session, setSession] = useState(null);

  useEffect(() => {
    const loadSession = async () => {
      const saved = await AsyncStorage.getItem(SESSION_KEY);
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          if (parsed?.token) {
            setSession(parsed);
          } else {
            // Backward compatibility for older token-only storage.
            setSession({ token: saved, username: "unknown", role: "unknown", district: null });
          }
        } catch {
          setSession({ token: saved, username: "unknown", role: "unknown", district: null });
        }
      }
      setBooting(false);
    };
    loadSession();
  }, []);

  const onLoginSuccess = async (auth) => {
    const nextSession = {
      token: auth.api_token,
      username: auth.username,
      role: auth.role,
      district: auth.district
    };
    await AsyncStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
    setSession(nextSession);
  };

  const onLogout = async () => {
    await AsyncStorage.removeItem(SESSION_KEY);
    setSession(null);
  };

  if (booting) {
    return (
      <SafeAreaView style={styles.centered}>
        <ActivityIndicator size="large" color="#2155ea" />
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <View style={styles.inner}>
        {session?.token ? (
          <HomeScreen token={session.token} user={session} onLogout={onLogout} />
        ) : (
          <LoginScreen onLoginSuccess={onLoginSuccess} />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0b1738"
  },
  inner: {
    flex: 1
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#0b1738"
  }
});
