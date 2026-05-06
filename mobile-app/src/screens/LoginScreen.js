import React, { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Image,
  ActivityIndicator,
  Animated,
  Easing,
  KeyboardAvoidingView,
  Platform,
  Pressable
} from "react-native";
import { login } from "../api/client";

export default function LoginScreen({ onLoginSuccess }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const passwordRef = useRef(null);
  const floatAnim = useRef(new Animated.Value(0)).current;
  const pulseAnim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const floatLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(floatAnim, {
          toValue: 1,
          duration: 7000,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true
        }),
        Animated.timing(floatAnim, {
          toValue: 0,
          duration: 7000,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: true
        })
      ])
    );

    const pulseLoop = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 4000,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true
        }),
        Animated.timing(pulseAnim, {
          toValue: 0,
          duration: 4000,
          easing: Easing.inOut(Easing.quad),
          useNativeDriver: true
        })
      ])
    );

    floatLoop.start();
    pulseLoop.start();

    return () => {
      floatLoop.stop();
      pulseLoop.stop();
    };
  }, [floatAnim, pulseAnim]);

  const orb1TranslateY = floatAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, -18]
  });
  const orb2TranslateY = floatAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 22]
  });
  const orbScale = pulseAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 1.12]
  });
  const orbOpacity = pulseAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0.35, 0.6]
  });

  const onLogin = async () => {
    setError("");
    const u = username.trim();
    if (!u || !password) {
      setError("Enter username and password.");
      return;
    }
    setLoading(true);
    try {
      const result = await login(u, password);
      onLoginSuccess(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={Platform.OS === "ios" ? 64 : 0}
    >
    <View style={styles.container}>
      <Animated.View
        pointerEvents="none"
        style={[
          styles.orb,
          styles.orbTop,
          {
            opacity: orbOpacity,
            transform: [{ translateY: orb1TranslateY }, { scale: orbScale }]
          }
        ]}
      />
      <Animated.View
        pointerEvents="none"
        style={[
          styles.orb,
          styles.orbBottom,
          {
            opacity: orbOpacity,
            transform: [{ translateY: orb2TranslateY }]
          }
        ]}
      />

      <Image source={require("../../assets/logo1.png")} style={styles.logo} />
      <Text style={styles.title}>e-OSEWS Mobile</Text>
      <Text style={styles.subtitle}>One Health Surveillance Access</Text>

      <TextInput
        style={styles.input}
        placeholder="Username"
        placeholderTextColor="#7f92bd"
        value={username}
        onChangeText={setUsername}
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="username"
        textContentType="username"
        returnKeyType="next"
        blurOnSubmit={false}
        onSubmitEditing={() => passwordRef.current?.focus()}
        editable={!loading}
      />
      <TextInput
        ref={passwordRef}
        style={styles.input}
        placeholder="Password"
        placeholderTextColor="#7f92bd"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoComplete="password"
        textContentType="password"
        returnKeyType="go"
        onSubmitEditing={onLogin}
        editable={!loading}
      />
      {error ? <Text style={styles.error}>{error}</Text> : null}
      <Pressable
        style={({ pressed }) => [styles.button, pressed && styles.buttonPressed, loading && styles.buttonDisabled]}
        onPress={onLogin}
        disabled={loading}
      >
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Sign In</Text>}
      </Pressable>
    </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: {
    flex: 1,
    padding: 24,
    justifyContent: "center",
    backgroundColor: "#0b1738",
    overflow: "hidden"
  },
  orb: {
    position: "absolute",
    borderRadius: 9999
  },
  orbTop: {
    width: 260,
    height: 260,
    backgroundColor: "#2749ff",
    top: -80,
    right: -50
  },
  orbBottom: {
    width: 300,
    height: 300,
    backgroundColor: "#0ea5e9",
    bottom: -120,
    left: -70
  },
  logo: {
    width: 260,
    height: 120,
    alignSelf: "center",
    marginBottom: 14,
    resizeMode: "contain"
  },
  title: {
    color: "#ffffff",
    fontSize: 28,
    fontWeight: "800",
    textAlign: "center"
  },
  subtitle: {
    color: "#aac1ef",
    textAlign: "center",
    marginBottom: 20
  },
  input: {
    backgroundColor: "#15254f",
    color: "#e5edff",
    borderColor: "#223b79",
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 10
  },
  button: {
    backgroundColor: "#295de9",
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: "center",
    marginTop: 6
  },
  buttonPressed: {
    opacity: 0.88
  },
  buttonDisabled: {
    opacity: 0.65
  },
  buttonText: {
    color: "#fff",
    fontWeight: "700"
  },
  error: {
    color: "#ff7b7b",
    marginBottom: 6
  }
});
