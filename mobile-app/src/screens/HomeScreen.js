import React, { useCallback, useEffect, useState } from "react";
import {
  ScrollView,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl
} from "react-native";
import * as Location from "expo-location";
import * as Network from "expo-network";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Picker } from "@react-native-picker/picker";
import {
  getFlaggedEvents,
  getFlaggedEventsSummary,
  getPendingEventCounts,
  getSummary,
  submitEvent,
  submitUssdReport,
  syncPendingEvents,
  updateEventValidationStatus
} from "../api/client";

const starter = {
  reporter_name: "",
  reporter_contact: "",
  reporter_role: "midwife",
  district: "Kabale",
  parish: "Kitumba",
  species_or_patient: "pregnant_woman",
  syndrome: "fever and miscarriage",
  gestational_weeks: "24",
  animal_exposure: "true",
  rainfall_index: "0.8",
  ndvi_index: "0.7",
  temperature_c: "31",
  latitude: "-1.25",
  longitude: "29.98"
};

const roleOptions = ["midwife", "clinician", "vet", "vht"];
const districtOptions = ["Kabale", "Rubanda", "Isingiro"];
const parishByDistrict = {
  Kabale: ["Kitumba", "Kyanamira", "Buhara"],
  Rubanda: ["Muko", "Hamurwa", "Bufundi"],
  Isingiro: ["Nyakagyeme", "Kabuyanda", "Masha"]
};
const speciesByRole = {
  midwife: ["pregnant_woman"],
  clinician: ["pregnant_woman"],
  vet: ["cattle", "goat", "sheep"],
  vht: ["pregnant_woman", "cattle", "goat", "sheep"]
};
const syndromeByRole = {
  midwife: ["fever and miscarriage", "haemorrhagic fever", "febrile illness in pregnancy"],
  clinician: ["haemorrhagic fever", "severe febrile illness", "suspected RVF case"],
  vet: ["animal abortion", "sudden animal death", "livestock fever cluster"],
  vht: ["fever in pregnant woman", "animal abortion", "sudden animal death"]
};
const pageOrder = ["dashboard", "event", "ussd", "validation", "account"];
const EVENT_DRAFT_KEY = "EOSEWS_EVENT_DRAFT_V1";
const USSD_DRAFT_KEY = "EOSEWS_USSD_DRAFT_V1";
const ussdStarter = {
  district: "Kabale",
  parish: "Kitumba",
  syndrome: "animal abortion",
  species: "cattle",
  reporter_role: "vht",
  animal_exposure: "true"
};

function getDefaultPageForRole(role) {
  if (role === "vht") return "ussd";
  if (role === "vet") return "event";
  if (role === "district") return "validation";
  return "dashboard";
}

function defaultAnimalExposure(species, role) {
  if (species === "pregnant_woman") return "false";
  if (role === "vet") return "true";
  if (species === "cattle" || species === "goat" || species === "sheep") return "true";
  return "false";
}

export default function HomeScreen({ token, user, onLogout }) {
  const [summary, setSummary] = useState(null);
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState(starter);
  const [syncStats, setSyncStats] = useState({ pending: 0, failed: 0 });
  const [flaggedEvents, setFlaggedEvents] = useState([]);
  const [flagFilter, setFlagFilter] = useState("flagged");
  const [flagCounts, setFlagCounts] = useState({ flagged: 0, reviewed: 0, dismissed: 0, all: 0 });
  const [gps, setGps] = useState(null);
  const [gpsLoading, setGpsLoading] = useState(false);
  const [gpsError, setGpsError] = useState("");
  const [ipAddress, setIpAddress] = useState("unknown");
  const [activePage, setActivePage] = useState(getDefaultPageForRole(user?.role));
  const [eventErrors, setEventErrors] = useState([]);
  const [ussdErrors, setUssdErrors] = useState([]);
  const [refreshing, setRefreshing] = useState(false);
  const [ussdForm, setUssdForm] = useState(ussdStarter);
  const [draftsHydrated, setDraftsHydrated] = useState(false);

  const refreshSyncStats = async () => {
    const counts = await getPendingEventCounts();
    setSyncStats(counts);
  };

  useEffect(() => {
    refreshSyncStats();
  }, []);

  useEffect(() => {
    let mounted = true;
    const hydrateDrafts = async () => {
      try {
        const [eventRaw, ussdRaw] = await Promise.all([
          AsyncStorage.getItem(EVENT_DRAFT_KEY),
          AsyncStorage.getItem(USSD_DRAFT_KEY)
        ]);
        if (!mounted) return;
        if (eventRaw) {
          try {
            const parsed = JSON.parse(eventRaw);
            if (parsed && typeof parsed === "object") {
              setForm((prev) => ({ ...prev, ...parsed }));
            }
          } catch {
            // Ignore malformed local draft payload.
          }
        }
        if (ussdRaw) {
          try {
            const parsed = JSON.parse(ussdRaw);
            if (parsed && typeof parsed === "object") {
              setUssdForm((prev) => ({ ...prev, ...parsed }));
            }
          } catch {
            // Ignore malformed local draft payload.
          }
        }
      } finally {
        if (mounted) setDraftsHydrated(true);
      }
    };
    hydrateDrafts();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (user?.username && !form.reporter_name) {
      setForm((prev) => ({ ...prev, reporter_name: user.username }));
    }
  }, [user?.username]);

  useEffect(() => {
    if (!draftsHydrated) return;
    const timer = setTimeout(() => {
      AsyncStorage.setItem(EVENT_DRAFT_KEY, JSON.stringify(form)).catch(() => {});
    }, 250);
    return () => clearTimeout(timer);
  }, [form, draftsHydrated]);

  useEffect(() => {
    if (!draftsHydrated) return;
    const timer = setTimeout(() => {
      AsyncStorage.setItem(USSD_DRAFT_KEY, JSON.stringify(ussdForm)).catch(() => {});
    }, 250);
    return () => clearTimeout(timer);
  }, [ussdForm, draftsHydrated]);

  const refreshRemoteData = useCallback(
    async (opts = { showErrors: false }) => {
      try {
        const [rows, counts, data] = await Promise.all([
          getFlaggedEvents(token, 10, flagFilter),
          getFlaggedEventsSummary(token),
          getSummary(token)
        ]);
        setFlaggedEvents(rows);
        setFlagCounts(counts);
        setSummary(data);
        await refreshSyncStats();
      } catch (e) {
        if (opts.showErrors) {
          setMsg(e.message || "Refresh failed.");
        }
      }
    },
    [token, flagFilter]
  );

  useEffect(() => {
    refreshRemoteData({ showErrors: false });
  }, [refreshRemoteData]);

  useEffect(() => {
    const timer = setInterval(() => {
      refreshRemoteData({ showErrors: false });
    }, 30000);
    return () => clearInterval(timer);
  }, [refreshRemoteData]);

  const onPullRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refreshRemoteData({ showErrors: true });
    } finally {
      setRefreshing(false);
    }
  }, [refreshRemoteData]);

  const refreshGps = async () => {
    setGpsError("");
    setGpsLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        setGpsError("Location permission denied. Enable GPS permission for accurate coordinates.");
        return;
      }
      const current = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced
      });
      setGps({
        latitude: current.coords.latitude,
        longitude: current.coords.longitude,
        accuracy: current.coords.accuracy
      });
    } catch (e) {
      setGpsError(e.message || "Unable to get GPS location.");
    } finally {
      setGpsLoading(false);
    }
  };

  useEffect(() => {
    refreshGps();
  }, []);

  useEffect(() => {
    let mounted = true;
    const pullIp = async () => {
      try {
        const ip = await Network.getIpAddressAsync();
        if (mounted) setIpAddress(ip || "unknown");
      } catch {
        if (mounted) setIpAddress("unknown");
      }
    };
    pullIp();
    const timer = setInterval(pullIp, 30000);
    return () => {
      mounted = false;
      clearInterval(timer);
    };
  }, []);

  const loadSummary = async () => {
    setMsg("");
    try {
      const sync = await syncPendingEvents(token);
      await refreshSyncStats();
      const data = await getSummary(token);
      setSummary(data);
      if (sync.synced > 0) {
        setMsg(`Synced ${sync.synced} queued event(s).`);
      }
    } catch (e) {
      setMsg(e.message);
    }
  };

  const sendEvent = async () => {
    setMsg("");
    setEventErrors([]);
    const errors = [];
    if (!form.reporter_name) errors.push("Event: reporter name is required.");
    if (!form.reporter_contact) errors.push("Event: reporter contact is required.");
    if (!form.reporter_role) errors.push("Event: reporter role is required.");
    if (!form.district) errors.push("Event: district is required.");
    if (!form.parish) errors.push("Event: parish is required.");
    if (!form.species_or_patient) errors.push("Event: species/patient is required.");
    if (!form.syndrome) errors.push("Event: syndrome is required.");

    const gest = Number(form.gestational_weeks || 0);
    if (form.gestational_weeks && (Number.isNaN(gest) || gest < 0 || gest > 45)) {
      errors.push("Event: gestational weeks must be between 0 and 45.");
    }
    const rainfall = Number(form.rainfall_index || 0);
    if (Number.isNaN(rainfall) || rainfall < 0 || rainfall > 1) {
      errors.push("Event: rainfall_index must be between 0 and 1.");
    }
    const ndvi = Number(form.ndvi_index || 0);
    if (Number.isNaN(ndvi) || ndvi < 0 || ndvi > 1) {
      errors.push("Event: ndvi_index must be between 0 and 1.");
    }
    const temp = Number(form.temperature_c || 0);
    if (Number.isNaN(temp) || temp < -50 || temp > 80) {
      errors.push("Event: temperature_c must be between -50 and 80.");
    }
    if (errors.length) {
      setEventErrors(errors);
      setMsg("Please correct event form errors before submit.");
      return;
    }
    try {
      const payload = {
        ...form,
        gestational_weeks: Number(form.gestational_weeks || 0),
        animal_exposure: form.animal_exposure === "true",
        rainfall_index: Number(form.rainfall_index || 0),
        ndvi_index: Number(form.ndvi_index || 0),
        temperature_c: Number(form.temperature_c || 0),
        latitude: gps?.latitude ?? Number(form.latitude || 0),
        longitude: gps?.longitude ?? Number(form.longitude || 0),
        ip_address: ipAddress
      };
      const result = await submitEvent(token, payload);
      await refreshSyncStats();
      if (result.sync_status === "pending") {
        setMsg("No network/server unreachable. Event saved and queued for sync.");
      } else {
        setMsg(`Event submitted (ID ${result.id})`);
      }
      await AsyncStorage.removeItem(EVENT_DRAFT_KEY);
      setForm((prev) => ({
        ...starter,
        reporter_name: user?.username || prev.reporter_name || "",
        reporter_role: prev.reporter_role || "midwife",
        district: prev.district || "Kabale",
        parish: parishByDistrict[prev.district || "Kabale"]?.[0] || "Kitumba"
      }));
    } catch (e) {
      setMsg(e.message);
    }
  };

  const loadFlagged = async () => {
    setMsg("");
    try {
      const [rows, counts] = await Promise.all([
        getFlaggedEvents(token, 10, flagFilter),
        getFlaggedEventsSummary(token)
      ]);
      setFlaggedEvents(rows);
      setFlagCounts(counts);
      setMsg(rows.length ? `Loaded ${rows.length} ${flagFilter} record(s).` : `No ${flagFilter} records found.`);
    } catch (e) {
      setMsg(e.message);
    }
  };

  const setFlagStatus = async (eventId, status) => {
    setMsg("");
    try {
      await updateEventValidationStatus(token, eventId, status);
      await loadFlagged();
      setMsg(`Record #${eventId} marked as ${status}.`);
    } catch (e) {
      setMsg(e.message);
    }
  };

  const applyFlagFilter = async (status) => {
    setFlagFilter(status);
    setMsg("");
    try {
      const [rows, counts] = await Promise.all([
        getFlaggedEvents(token, 10, status),
        getFlaggedEventsSummary(token)
      ]);
      setFlaggedEvents(rows);
      setFlagCounts(counts);
      setMsg(rows.length ? `Loaded ${rows.length} ${status} record(s).` : `No ${status} records found.`);
    } catch (e) {
      setMsg(e.message);
    }
  };

  const setField = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));
  const setUssdField = (key, value) => setUssdForm((prev) => ({ ...prev, [key]: value }));
  const filterStatuses = ["flagged", "reviewed", "dismissed", "all"];
  const lastGpsText = gps ? `${gps.latitude.toFixed(5)}, ${gps.longitude.toFixed(5)}` : "Not captured";
  const eventParishOptions = parishByDistrict[form.district] || ["Kitumba"];
  const ussdParishOptions = parishByDistrict[ussdForm.district] || ["Kitumba"];
  const eventSyndromeOptions = syndromeByRole[form.reporter_role] || syndromeByRole.midwife;
  const ussdSyndromeOptions = syndromeByRole[ussdForm.reporter_role] || syndromeByRole.vht;
  const eventSpeciesOptions = speciesByRole[form.reporter_role] || ["pregnant_woman"];
  const ussdSpeciesOptions = speciesByRole[ussdForm.reporter_role] || ["pregnant_woman"];
  const userRole = user?.role || "unknown";
  const canManageValidation = ["admin", "district", "clinician", "midwife", "vet"].includes(userRole);
  const canUseUssdScreen = ["admin", "district", "vet", "vht"].includes(userRole);
  const canUseEventScreen = ["admin", "district", "midwife", "clinician", "vet", "vht"].includes(userRole);
  const roleScopes = {
    admin: "National scope across all districts.",
    district: `District scope limited to ${user?.district || "assigned district"}.`,
    midwife: "Clinical maternal reporting and verification.",
    clinician: "Facility-level case reporting and review.",
    vet: "Animal health reporting and zoonotic risk signals.",
    vht: "Community signal reporting and rapid escalation."
  };
  const visiblePages = pageOrder.filter((page) => {
    if (page === "validation") return canManageValidation;
    if (page === "ussd") return canUseUssdScreen;
    if (page === "event") return canUseEventScreen;
    return true;
  });

  useEffect(() => {
    if (!eventParishOptions.includes(form.parish)) {
      setForm((prev) => ({ ...prev, parish: eventParishOptions[0] }));
    }
  }, [form.district]);

  useEffect(() => {
    if (!ussdParishOptions.includes(ussdForm.parish)) {
      setUssdForm((prev) => ({ ...prev, parish: ussdParishOptions[0] }));
    }
  }, [ussdForm.district]);

  useEffect(() => {
    if (!eventSyndromeOptions.includes(form.syndrome)) {
      setForm((prev) => ({ ...prev, syndrome: eventSyndromeOptions[0] }));
    }
  }, [form.reporter_role]);

  useEffect(() => {
    if (!ussdSyndromeOptions.includes(ussdForm.syndrome)) {
      setUssdForm((prev) => ({ ...prev, syndrome: ussdSyndromeOptions[0] }));
    }
  }, [ussdForm.reporter_role]);

  useEffect(() => {
    if (!eventSpeciesOptions.includes(form.species_or_patient)) {
      setForm((prev) => ({ ...prev, species_or_patient: eventSpeciesOptions[0] }));
    }
  }, [form.reporter_role]);

  useEffect(() => {
    if (!ussdSpeciesOptions.includes(ussdForm.species)) {
      setUssdForm((prev) => ({ ...prev, species: ussdSpeciesOptions[0] }));
    }
  }, [ussdForm.reporter_role]);

  useEffect(() => {
    setForm((prev) => ({
      ...prev,
      animal_exposure: defaultAnimalExposure(prev.species_or_patient, prev.reporter_role)
    }));
  }, [form.species_or_patient, form.reporter_role]);

  useEffect(() => {
    setUssdForm((prev) => ({
      ...prev,
      animal_exposure: defaultAnimalExposure(prev.species, prev.reporter_role)
    }));
  }, [ussdForm.species, ussdForm.reporter_role]);

  useEffect(() => {
    const preferred = getDefaultPageForRole(userRole);
    if (visiblePages.includes(preferred)) {
      setActivePage(preferred);
      return;
    }
    if (!visiblePages.includes(activePage) && visiblePages.length) {
      setActivePage(visiblePages[0]);
    }
  }, [userRole]);

  const submitUssd = async () => {
    setMsg("");
    setUssdErrors([]);
    const errors = [];
    if (!ussdForm.district) errors.push("USSD: district is required.");
    if (!ussdForm.parish) errors.push("USSD: parish is required.");
    if (!ussdForm.syndrome) errors.push("USSD: syndrome is required.");
    if (!ussdForm.species) errors.push("USSD: species is required.");
    if (!ussdForm.reporter_role) errors.push("USSD: reporter role is required.");
    if (errors.length) {
      setUssdErrors(errors);
      setMsg("Please correct USSD form errors before submit.");
      return;
    }
    try {
      const result = await submitUssdReport(token, {
        ...ussdForm,
        animal_exposure: ussdForm.animal_exposure === "true",
        ip_address: ipAddress
      });
      setMsg(`USSD signal accepted (Event ID ${result.event?.id || "n/a"}).`);
      await AsyncStorage.removeItem(USSD_DRAFT_KEY);
      setUssdForm(ussdStarter);
      await loadSummary();
    } catch (e) {
      setMsg(e.message);
    }
  };

  const renderCounterRow = () => (
    <View style={styles.counterRow}>
      <View style={styles.counterPillDanger}>
        <Text style={styles.counterPillText}>Flagged {flagCounts.flagged}</Text>
      </View>
      <View style={styles.counterPillInfo}>
        <Text style={styles.counterPillText}>Reviewed {flagCounts.reviewed}</Text>
      </View>
      <View style={styles.counterPillWarn}>
        <Text style={styles.counterPillText}>Dismissed {flagCounts.dismissed}</Text>
      </View>
    </View>
  );

  const renderFilterChips = () => (
    <View style={styles.filterRow}>
      {filterStatuses.map((status) => (
        <TouchableOpacity
          key={status}
          style={flagFilter === status ? styles.filterChipActive : styles.filterChip}
          onPress={() => applyFlagFilter(status)}
        >
          <Text style={styles.filterChipText}>
            {status} ({status === "all" ? flagCounts.all : flagCounts[status] || 0})
          </Text>
        </TouchableOpacity>
      ))}
    </View>
  );

  const renderPageTabs = () => (
    <View style={styles.tabRow}>
      {visiblePages.map((page) => {
        return (
          <TouchableOpacity
            key={page}
            style={activePage === page ? styles.tabActive : styles.tab}
            onPress={() => setActivePage(page)}
          >
            <Text style={styles.tabText}>{page}</Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={onPullRefresh}
          tintColor="#8fb7ff"
          colors={["#8fb7ff", "#60a5fa"]}
        />
      }
    >
      <View style={styles.hero}>
        <View>
          <Text style={styles.title}>e-OSEWS Field App</Text>
          <Text style={styles.subtitle}>One Health Surveillance</Text>
        </View>
        <View style={styles.userBadge}>
          <Text style={styles.userBadgeText}>{(user?.role || "user").toUpperCase()}</Text>
        </View>
      </View>
      {renderPageTabs()}

      {activePage === "dashboard" ? (
        <>
          <View style={styles.row}>
            <TouchableOpacity style={styles.secondaryBtn} onPress={loadSummary}>
              <Text style={styles.btnText}>Sync + Summary</Text>
            </TouchableOpacity>
            {canManageValidation ? (
              <TouchableOpacity style={styles.secondaryBtn} onPress={loadFlagged}>
                <Text style={styles.btnText}>Validation Center</Text>
              </TouchableOpacity>
            ) : null}
          </View>
          <Text style={styles.syncMeta}>
            Queue status: Pending {syncStats.pending} | Failed {syncStats.failed}
          </Text>
          <View style={styles.card}>
            <Text style={styles.cardTitle}>Operations Overview</Text>
            <Text style={styles.cardSubtle}>Role scope: {roleScopes[userRole] || "Standard access scope."}</Text>
          </View>
          {summary ? (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Live Summary</Text>
              <Text style={styles.cardSubtle}>District: {summary.district || "All"}</Text>
              <View style={styles.statGrid}>
                <View style={styles.statTile}>
                  <Text style={styles.statValue}>{summary.total_events}</Text>
                  <Text style={styles.statLabel}>Events</Text>
                </View>
                <View style={styles.statTile}>
                  <Text style={styles.statValue}>{summary.total_alerts}</Text>
                  <Text style={styles.statLabel}>Alerts</Text>
                </View>
                <View style={styles.statTile}>
                  <Text style={styles.statValue}>{summary.high_risk_events}</Text>
                  <Text style={styles.statLabel}>High Risk</Text>
                </View>
                <View style={styles.statTile}>
                  <Text style={styles.statValue}>{summary.flagged_events || 0}</Text>
                  <Text style={styles.statLabel}>Data Flags</Text>
                </View>
              </View>
            </View>
          ) : (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Live Summary</Text>
              <Text style={styles.cardLine}>Tap "Sync + Summary" to load current metrics.</Text>
            </View>
          )}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>GPS + Network</Text>
            {gpsLoading ? (
              <ActivityIndicator color="#8fb7ff" />
            ) : gps ? (
              <>
                <Text style={styles.cardLine}>Latitude: {gps.latitude.toFixed(6)}</Text>
                <Text style={styles.cardLine}>Longitude: {gps.longitude.toFixed(6)}</Text>
                <Text style={styles.cardLine}>Accuracy: {Math.round(gps.accuracy || 0)} m</Text>
              </>
            ) : (
              <Text style={styles.flagNote}>{gpsError || "GPS not loaded yet."}</Text>
            )}
            <Text style={styles.cardSubtle}>Last capture: {lastGpsText}</Text>
            <Text style={styles.cardSubtle}>Device IP: {ipAddress}</Text>
            <TouchableOpacity style={styles.secondaryBtn} onPress={refreshGps}>
              <Text style={styles.btnText}>Refresh GPS</Text>
            </TouchableOpacity>
          </View>
        </>
      ) : null}

      {activePage === "event" ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Event Submission</Text>
          <Text style={styles.cardSubtle}>Structured human/animal report using role-based syndrome options.</Text>
          {eventErrors.length ? (
            <View style={styles.errorBox}>
              {eventErrors.map((err) => (
                <Text key={err} style={styles.errorLine}>- {err}</Text>
              ))}
            </View>
          ) : null}
          <Text style={styles.fieldLabel}>Reporter name</Text>
          <TextInput
            style={styles.input}
            value={form.reporter_name}
            onChangeText={(v) => setField("reporter_name", v)}
            placeholder="Full name"
            placeholderTextColor="#7f92bd"
          />
          <Text style={styles.fieldLabel}>Reporter contact</Text>
          <TextInput
            style={styles.input}
            value={form.reporter_contact}
            onChangeText={(v) => setField("reporter_contact", v)}
            placeholder="Phone number"
            placeholderTextColor="#7f92bd"
            keyboardType="phone-pad"
          />
          <Text style={styles.fieldLabel}>Reporter role</Text>
          <Picker selectedValue={form.reporter_role} onValueChange={(v) => setField("reporter_role", v)} style={styles.picker}>
            {roleOptions.map((item) => (
              <Picker.Item key={item} label={item} value={item} />
            ))}
          </Picker>
          <Text style={styles.fieldLabel}>District</Text>
          <Picker selectedValue={form.district} onValueChange={(v) => setField("district", v)} style={styles.picker}>
            {districtOptions.map((item) => (
              <Picker.Item key={item} label={item} value={item} />
            ))}
          </Picker>
          <Text style={styles.fieldLabel}>Parish</Text>
          <Picker selectedValue={form.parish} onValueChange={(v) => setField("parish", v)} style={styles.picker}>
            {eventParishOptions.map((item) => (
              <Picker.Item key={item} label={item} value={item} />
            ))}
          </Picker>
          <Text style={styles.fieldLabel}>Species / Patient</Text>
          <Picker selectedValue={form.species_or_patient} onValueChange={(v) => setField("species_or_patient", v)} style={styles.picker}>
            {eventSpeciesOptions.map((item) => (
              <Picker.Item key={item} label={item} value={item} />
            ))}
          </Picker>
          <Text style={styles.fieldLabel}>Syndrome</Text>
          <Picker selectedValue={form.syndrome} onValueChange={(v) => setField("syndrome", v)} style={styles.picker}>
            {eventSyndromeOptions.map((item) => (
              <Picker.Item key={item} label={item} value={item} />
            ))}
          </Picker>
          <Text style={styles.fieldLabel}>Animal Exposure</Text>
          <Picker selectedValue={form.animal_exposure} onValueChange={(v) => setField("animal_exposure", v)} style={styles.picker}>
            <Picker.Item label="true" value="true" />
            <Picker.Item label="false" value="false" />
          </Picker>
          <Text style={styles.helperText}>
            Auto-set from role/species; you can still override if field conditions differ.
          </Text>
          <TextInput
            style={styles.input}
            value={form.gestational_weeks}
            onChangeText={(v) => setField("gestational_weeks", v)}
            placeholder="gestational_weeks"
            placeholderTextColor="#7f92bd"
            keyboardType="number-pad"
          />
          <TextInput
            style={styles.input}
            value={form.rainfall_index}
            onChangeText={(v) => setField("rainfall_index", v)}
            placeholder="rainfall_index (0-1)"
            placeholderTextColor="#7f92bd"
            keyboardType="decimal-pad"
          />
          <TextInput
            style={styles.input}
            value={form.ndvi_index}
            onChangeText={(v) => setField("ndvi_index", v)}
            placeholder="ndvi_index (0-1)"
            placeholderTextColor="#7f92bd"
            keyboardType="decimal-pad"
          />
          <TextInput
            style={styles.input}
            value={form.temperature_c}
            onChangeText={(v) => setField("temperature_c", v)}
            placeholder="temperature_c"
            placeholderTextColor="#7f92bd"
            keyboardType="decimal-pad"
          />
          <TouchableOpacity style={styles.primaryBtn} onPress={sendEvent}>
            <Text style={styles.btnText}>Send Event</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {activePage === "validation" && canManageValidation && flaggedEvents.length ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Validation Records ({flagFilter})</Text>
          {renderCounterRow()}
          {renderFilterChips()}
          {flaggedEvents.map((item) => {
            const notes = Array.isArray(item.validation_notes) ? item.validation_notes.join(", ") : item.validation_notes;
            return (
              <View key={item.id} style={styles.flagItemCard}>
                <Text style={styles.cardLineStrong}>
                  #{item.id} {item.district}/{item.parish}
                </Text>
                <Text style={styles.cardLine}>Status: {item.validation_status || "ok"}</Text>
                <Text style={styles.cardLine}>Syndrome: {item.syndrome}</Text>
                <Text style={styles.flagNote}>Flags: {notes || "n/a"}</Text>
                <View style={styles.flagActions}>
                  <TouchableOpacity style={styles.actionBtn} onPress={() => setFlagStatus(item.id, "reviewed")}>
                    <Text style={styles.actionText}>Mark Reviewed</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={styles.actionBtnMuted} onPress={() => setFlagStatus(item.id, "dismissed")}>
                    <Text style={styles.actionText}>Dismiss</Text>
                  </TouchableOpacity>
                </View>
              </View>
            );
          })}
        </View>
      ) : null}
      {activePage === "validation" && canManageValidation && !flaggedEvents.length && ["flagged", "reviewed", "dismissed", "all"].includes(flagFilter) ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Validation Records ({flagFilter})</Text>
          {renderCounterRow()}
          {renderFilterChips()}
          <Text style={styles.cardLine}>No records in this view.</Text>
        </View>
      ) : null}

      {activePage === "ussd" && canUseUssdScreen ? (
        <View style={styles.card}>
        <Text style={styles.cardTitle}>USSD Code Submission</Text>
        <Text style={styles.cardSubtle}>Submit community signal using structured USSD-style fields.</Text>
        {ussdErrors.length ? (
          <View style={styles.errorBox}>
            {ussdErrors.map((err) => (
              <Text key={err} style={styles.errorLine}>- {err}</Text>
            ))}
          </View>
        ) : null}
        <Text style={styles.fieldLabel}>District</Text>
        <Picker selectedValue={ussdForm.district} onValueChange={(v) => setUssdField("district", v)} style={styles.picker}>
          {districtOptions.map((item) => (
            <Picker.Item key={item} label={item} value={item} />
          ))}
        </Picker>
        <Text style={styles.fieldLabel}>Parish</Text>
        <Picker selectedValue={ussdForm.parish} onValueChange={(v) => setUssdField("parish", v)} style={styles.picker}>
          {ussdParishOptions.map((item) => (
            <Picker.Item key={item} label={item} value={item} />
          ))}
        </Picker>
        <Text style={styles.fieldLabel}>Syndrome</Text>
        <Picker selectedValue={ussdForm.syndrome} onValueChange={(v) => setUssdField("syndrome", v)} style={styles.picker}>
          {ussdSyndromeOptions.map((item) => (
            <Picker.Item key={item} label={item} value={item} />
          ))}
        </Picker>
        <Text style={styles.fieldLabel}>Species</Text>
        <Picker selectedValue={ussdForm.species} onValueChange={(v) => setUssdField("species", v)} style={styles.picker}>
          {ussdSpeciesOptions.map((item) => (
            <Picker.Item key={item} label={item} value={item} />
          ))}
        </Picker>
        <Text style={styles.fieldLabel}>Reporter Role</Text>
        <Picker selectedValue={ussdForm.reporter_role} onValueChange={(v) => setUssdField("reporter_role", v)} style={styles.picker}>
          {roleOptions.map((item) => (
            <Picker.Item key={item} label={item} value={item} />
          ))}
        </Picker>
        <Text style={styles.fieldLabel}>Animal Exposure</Text>
        <Picker selectedValue={ussdForm.animal_exposure} onValueChange={(v) => setUssdField("animal_exposure", v)} style={styles.picker}>
          <Picker.Item label="true" value="true" />
          <Picker.Item label="false" value="false" />
        </Picker>
        <Text style={styles.helperText}>
          Auto-set from reporter role and species for faster USSD signal entry.
        </Text>
        <TouchableOpacity style={styles.primaryBtn} onPress={submitUssd}>
          <Text style={styles.btnText}>Submit USSD Signal</Text>
        </TouchableOpacity>
        </View>
      ) : null}

      {activePage === "account" ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Account & Role Guidance</Text>
          <Text style={styles.cardLine}>Username: {user?.username || "Unknown"}</Text>
          <Text style={styles.cardLine}>Role: {userRole}</Text>
          <Text style={styles.cardLine}>District: {user?.district || "All"}</Text>
          <Text style={styles.cardSubtle}>Scope: {roleScopes[userRole] || "Standard scope."}</Text>
          <Text style={styles.qaQ}>Q: What should I do first?</Text>
          <Text style={styles.qaA}>A: Open Dashboard, confirm GPS/IP, then use Event or USSD page for submissions.</Text>
          <Text style={styles.qaQ}>Q: Why do I see different pages?</Text>
          <Text style={styles.qaA}>A: Pages and controls follow role hierarchy. Higher roles (admin/district) get broader controls.</Text>
          <Text style={styles.qaQ}>Q: How do I sign out?</Text>
          <Text style={styles.qaA}>A: Use the Logout button below to end your secured session.</Text>
          <TouchableOpacity style={styles.logoutBtn} onPress={onLogout}>
            <Text style={styles.btnText}>Logout</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      {msg ? <Text style={styles.message}>{msg}</Text> : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#09122f" },
  content: { padding: 16, paddingBottom: 40 },
  hero: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 12
  },
  title: { color: "#fff", fontWeight: "800", fontSize: 24, marginBottom: 12 },
  subtitle: { color: "#a8bce8", marginTop: -8 },
  userBadge: {
    backgroundColor: "#1f3a8a",
    borderColor: "#60a5fa",
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 6
  },
  userBadgeText: { color: "#dbeafe", fontSize: 12, fontWeight: "700" },
  tabRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 },
  tab: {
    borderWidth: 1,
    borderColor: "#355aa8",
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6
  },
  tabActive: {
    borderWidth: 1,
    borderColor: "#7fb1ff",
    backgroundColor: "#1e3a8a",
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6
  },
  tabText: { color: "#dbeafe", fontSize: 12, textTransform: "capitalize", fontWeight: "700" },
  row: { flexDirection: "row", gap: 8, marginBottom: 10 },
  syncMeta: { color: "#9fb8ec", marginBottom: 10 },
  card: {
    backgroundColor: "#101f47",
    borderColor: "#27438c",
    borderWidth: 1,
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 10,
    elevation: 2
  },
  cardTitle: { color: "#fff", fontWeight: "700", marginBottom: 8 },
  cardSubtle: { color: "#a9c0ee", marginBottom: 8 },
  counterRow: { flexDirection: "row", gap: 12, marginBottom: 8, flexWrap: "wrap" },
  counterPillDanger: {
    backgroundColor: "#7f1d1d",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5
  },
  counterPillInfo: {
    backgroundColor: "#1e3a8a",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5
  },
  counterPillWarn: {
    backgroundColor: "#78350f",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5
  },
  counterPillText: { color: "#fff", fontWeight: "700", fontSize: 12 },
  statGrid: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  statTile: {
    width: "48%",
    backgroundColor: "#162a5e",
    borderColor: "#2f4f99",
    borderWidth: 1,
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 10
  },
  statValue: { color: "#fff", fontSize: 20, fontWeight: "800" },
  statLabel: { color: "#b7c9f1", fontSize: 12, marginTop: 2 },
  cardLine: { color: "#bfd0f5", marginBottom: 2 },
  cardLineStrong: { color: "#e9f1ff", marginBottom: 2, fontWeight: "700" },
  flagItemCard: {
    backgroundColor: "#162a5e",
    borderColor: "#2f4f8c",
    borderWidth: 1,
    borderRadius: 10,
    padding: 10,
    marginBottom: 8
  },
  flagItem: {
    borderTopWidth: 1,
    borderTopColor: "#2f4f8c",
    paddingTop: 8,
    marginTop: 8
  },
  flagNote: { color: "#ffd798", marginBottom: 2 },
  filterRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 8 },
  filterChip: {
    borderWidth: 1,
    borderColor: "#375aa1",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5
  },
  filterChipActive: {
    borderWidth: 1,
    borderColor: "#60a5fa",
    backgroundColor: "#1e3a8a",
    borderRadius: 999,
    paddingHorizontal: 10,
    paddingVertical: 5
  },
  filterChipText: { color: "#dbeafe", fontSize: 12, textTransform: "capitalize" },
  flagActions: { flexDirection: "row", gap: 8, marginTop: 6 },
  actionBtn: {
    backgroundColor: "#2563eb",
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 7
  },
  actionBtnMuted: {
    backgroundColor: "#475569",
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 7
  },
  actionText: { color: "#fff", fontWeight: "600", fontSize: 12 },
  input: {
    backgroundColor: "#122453",
    color: "#f2f7ff",
    borderRadius: 9,
    borderWidth: 1,
    borderColor: "#284786",
    paddingHorizontal: 10,
    paddingVertical: 9,
    marginBottom: 8
  },
  picker: {
    backgroundColor: "#122453",
    color: "#f2f7ff",
    borderRadius: 9,
    borderWidth: 1,
    borderColor: "#284786",
    marginBottom: 8
  },
  fieldLabel: { color: "#b7c9f1", marginBottom: 4, marginTop: 4, fontSize: 12, fontWeight: "700" },
  helperText: { color: "#95addf", fontSize: 11, marginTop: -2, marginBottom: 8 },
  errorBox: {
    backgroundColor: "#4c1d1d",
    borderColor: "#ef4444",
    borderWidth: 1,
    borderRadius: 8,
    padding: 8,
    marginBottom: 8
  },
  errorLine: { color: "#fecaca", fontSize: 12, marginBottom: 2 },
  primaryBtn: {
    backgroundColor: "#2563eb",
    paddingVertical: 12,
    alignItems: "center",
    borderRadius: 10,
    marginTop: 4
  },
  secondaryBtn: {
    flex: 1,
    backgroundColor: "#1e40af",
    paddingVertical: 11,
    alignItems: "center",
    borderRadius: 10
  },
  logoutBtn: {
    flex: 1,
    backgroundColor: "#7f1d3f",
    paddingVertical: 11,
    alignItems: "center",
    borderRadius: 10
  },
  btnText: { color: "#fff", fontWeight: "700" },
  message: { color: "#cfe3ff", marginTop: 8 },
  qaQ: { color: "#dbeafe", fontWeight: "700", marginTop: 6 },
  qaA: { color: "#b9cff7", marginTop: 2 }
});
