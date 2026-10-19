import { StyleSheet, Text, View } from "react-native";

// Экран запуска демо появится в задаче 1.5.
export default function Index() {
  return (
    <View style={styles.root}>
      <Text>Финансовый бригадир</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, alignItems: "center", justifyContent: "center" },
});
